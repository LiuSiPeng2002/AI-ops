"""Read-only operations tools for both K8s and Linux system administration.

Two tools:
- kubectl_exec: kubectl command execution (permission based on user role)
- linux_exec: Linux system command execution (permission based on user role)

Permission model:
- viewer/operator: read-only only
- admin: write operations allowed (apply, delete, scale, restart, etc.)
- superadmin: full access including dangerous operations
"""

import contextvars
import re

import paramiko
from langchain_core.tools import tool

from config import settings

# ============================================================
# Role context (set by chat_service before graph execution)
# ============================================================

_current_role: contextvars.ContextVar[str] = contextvars.ContextVar("user_role", default="viewer")
# Dynamic machine config — overrides settings.k8s_master_* when set
_current_machine: contextvars.ContextVar[dict | None] = contextvars.ContextVar("machine_config", default=None)

# ============================================================
# SSH transport
# ============================================================

def _ssh_exec(command: str) -> str:
    """Execute a command on the target server via SSH. Returns stdout.

    Uses dynamic machine config from _current_machine context var if set,
    otherwise falls back to settings.k8s_master_* defaults.
    """
    machine = _current_machine.get()
    if machine:
        host = machine["host"]
        port = machine.get("port", 22)
        user = machine.get("username", "root")
        password = machine.get("password", "")
    else:
        host = settings.k8s_master_host
        port = settings.k8s_master_port
        user = settings.k8s_master_user
        password = settings.k8s_master_password

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host, port=port, username=user, password=password,
            timeout=settings.tool_exec_timeout,
        )
        stdin, stdout, stderr = client.exec_command(
            command,
            timeout=settings.tool_exec_timeout,
        )
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if exit_code != 0:
            return f"ERROR (exit={exit_code}): {err or output}"
        # Include stderr when stdout is empty (kubectl often prints "No resources found" to stderr)
        if not output.strip():
            return err.strip() or "(no output)"
        return output.strip()
    except Exception as exc:
        return f"SSH_ERROR: {exc}"
    finally:
        try:
            client.close()
        except Exception:
            pass


# ============================================================
# kubectl_exec
# ============================================================

# Read-only verbs (all roles)
READONLY_KUBECTL_VERBS = {
    "get", "describe", "logs", "top",
    "explain", "version", "cluster-info",
    "api-resources", "api-versions",
}

# Write verbs allowed for admin+
ADMIN_KUBECTL_VERBS = {
    "apply", "create", "delete", "edit", "patch",
    "scale", "label", "annotate", "rollout",
    "autoscale", "set",
}

# Dangerous verbs for superadmin only
SUPERADMIN_KUBECTL_VERBS = {
    "exec", "cp", "port-forward", "drain", "cordon",
    "uncordon", "taint", "certificate",
}

ROLLOUT_SAFE_SUB = {"status", "history"}
ROLLOUT_ADMIN_SUB = {"restart", "undo", "pause", "resume"}

FORBIDDEN_K8S_RE = re.compile(r"[;&`$(){}<>\\]")


def _get_kubectl_verbs(role: str) -> set[str]:
    """Get the set of allowed kubectl verbs for a given role."""
    if role == "superadmin":
        return READONLY_KUBECTL_VERBS | ADMIN_KUBECTL_VERBS | SUPERADMIN_KUBECTL_VERBS
    if role == "admin":
        return READONLY_KUBECTL_VERBS | ADMIN_KUBECTL_VERBS
    return READONLY_KUBECTL_VERBS


def _validate_kubectl(cmd: str, role: str) -> None:
    cmd = cmd.strip()
    # Length limit prevents buffer-overflow-style attacks
    if len(cmd) > settings.max_command_length:
        raise ValueError(
            f"Command too long ({len(cmd)} chars, max {settings.max_command_length})"
        )
    if FORBIDDEN_K8S_RE.search(cmd):
        raise ValueError("Shell metacharacters not allowed")

    parts = cmd.split()
    if not parts:
        raise ValueError("Empty command")

    verb = parts[0]
    allowed_verbs = _get_kubectl_verbs(role)

    if verb == "rollout":
        if len(parts) < 2:
            raise ValueError("rollout requires a subcommand")
        sub = parts[1]
        if role == "superadmin":
            allowed_subs = ROLLOUT_SAFE_SUB | ROLLOUT_ADMIN_SUB
        elif role == "admin":
            allowed_subs = ROLLOUT_SAFE_SUB | ROLLOUT_ADMIN_SUB
        else:
            allowed_subs = ROLLOUT_SAFE_SUB
        if sub not in allowed_subs:
            raise ValueError(
                f"rollout '{sub}' not allowed for role '{role}'. Allowed: {sorted(allowed_subs)}"
            )
        return

    if verb not in allowed_verbs:
        raise ValueError(
            f"kubectl '{verb}' not allowed for role '{role}'. "
            f"Allowed: {sorted(allowed_verbs)}"
        )


@tool
def kubectl_exec(command: str) -> str:
    """Execute a kubectl command on the K8s cluster.

    Args:
        command: kubectl command WITHOUT the 'kubectl' prefix.
                 Examples: "get pods -n default", "get deployments --all-namespaces",
                 "describe pod nginx", "top nodes", "logs pod-name --tail=100".

    Returns:
        The command output or error message.
    """
    role = _current_role.get()
    _validate_kubectl(command, role)
    return _ssh_exec(f"kubectl {command}")


# ============================================================
# linux_exec
# ============================================================

# Read-only commands (all roles)
LINUX_SAFE_COMMANDS = {
    # File system
    "ls", "cat", "head", "tail", "less", "find", "locate",
    "stat", "file", "md5sum", "sha256sum", "sha1sum",
    # Disk / mount
    "df", "du", "mount", "lsblk", "blkid",
    # System info
    "ps", "pstree", "top", "htop", "uptime",
    "free", "vmstat", "iostat", "mpstat",
    "dmesg",
    "uname", "hostname", "date", "who", "w", "last",
    "env", "printenv", "ulimit",
    # Network
    "ip", "ifconfig", "ss", "netstat", "ping",
    # Service management (read-only: only status/list-*)
    "systemctl",
    "journalctl",
    # Docker (read-only)
    "docker",
    # Misc
    "which", "whereis", "lsof",
    "lsmod", "lspci", "lsusb",
    "crontab",
    # Text search (read-only)
    "grep", "zgrep", "egrep",
    "diff", "comm",
    # JSON/YAML processing (read-only)
    "jq", "yq",
}

# Write commands for admin+
ADMIN_LINUX_COMMANDS = {
    # Package management
    "apt", "apt-get", "yum", "dnf",
    # Process management
    "kill", "killall",
    # File operations (write)
    "touch", "mkdir", "rm", "cp", "mv", "chmod", "chown",
    "ln", "tee", "echo", "printf",
    # Text editing
    "sed", "awk",
    # Service management (write)
    # systemctl/docker subcommands expanded below
    # Container management
    "curl", "wget",
    # System
    "sysctl", "modprobe", "swapoff", "swapon",
    # Scripting
    "python3", "python", "bash",
}

# Dangerous commands for superadmin only
SUPERADMIN_LINUX_COMMANDS = {
    "dd", "fdisk", "mkfs", "parted",
    "iptables", "firewall-cmd", "ufw",
    "reboot", "shutdown", "init",
    "crontab",  # edit mode
    "useradd", "usermod", "userdel",
    "passwd", "chpasswd",
}

# Commands allowed on the right side of a pipe (all roles)
PIPE_SAFE_COMMANDS = {
    "grep", "head", "tail", "wc", "sort", "uniq",
    "cut", "awk", "sed", "tr", "column",
}

# Subcommands allowed for multi-command tools
ALLOWED_SUBCOMMANDS = {
    "systemctl": {
        "status", "list-units", "list-unit-files",
        "is-active", "is-enabled", "show",
    },
    "docker": {
        "ps", "logs", "images", "stats", "inspect", "info", "version",
    },
    "crontab": {"-l"},
}

# Additional subcommands for admin+
ADMIN_SUBCOMMANDS = {
    "systemctl": {
        "start", "stop", "restart", "reload", "enable", "disable",
        "mask", "unmask",
    },
    "docker": {
        "start", "stop", "restart", "rm", "exec", "pull", "build",
        "network", "volume",
    },
    "crontab": {"-e"},
}

# Additional subcommands for superadmin
SUPERADMIN_SUBCOMMANDS = {
    "docker": {
        "rmi", "prune", "system",
    },
}

# Metacharacters blocked for all roles
FORBIDDEN_LINUX_RE = re.compile(r"[;&`$(){}<>\\]")
# Admin+ no metacharacter restrictions (never-matching sentinel)
FORBIDDEN_LINUX_WRITE_RE = re.compile(r"x^")


def _get_linux_commands(role: str) -> set[str]:
    """Get the set of allowed Linux commands for a given role."""
    base = LINUX_SAFE_COMMANDS
    if role == "superadmin":
        return base | ADMIN_LINUX_COMMANDS | SUPERADMIN_LINUX_COMMANDS
    if role == "admin":
        return base | ADMIN_LINUX_COMMANDS
    return base


def _get_allowed_subcommands(base_cmd: str, role: str) -> set[str]:
    """Get allowed subcommands for a given base command and role."""
    allowed = set(ALLOWED_SUBCOMMANDS.get(base_cmd, set()))
    if role in ("admin", "superadmin"):
        allowed |= ADMIN_SUBCOMMANDS.get(base_cmd, set())
    if role == "superadmin":
        allowed |= SUPERADMIN_SUBCOMMANDS.get(base_cmd, set())
    return allowed


def _validate_linux_command(token_list: list[str], role: str) -> None:
    """Validate a (possibly piped) Linux command token list."""
    if not token_list:
        raise ValueError("Empty command")

    base = token_list[0]
    allowed_cmds = _get_linux_commands(role)

    # Check base command
    if base not in allowed_cmds:
        raise ValueError(
            f"Command '{base}' not allowed for role '{role}' (not recognized or insufficient permissions)"
        )

    # Check subcommands for special commands
    if base in ALLOWED_SUBCOMMANDS or base in ADMIN_SUBCOMMANDS or base in SUPERADMIN_SUBCOMMANDS:
        allowed_subs = _get_allowed_subcommands(base, role)
        if allowed_subs:
            if len(token_list) < 2:
                raise ValueError(
                    f"'{base}' requires a subcommand. Allowed for '{role}': {sorted(allowed_subs)}"
                )
            sub = token_list[1]
            if sub not in allowed_subs:
                raise ValueError(
                    f"'{base} {sub}' not allowed for role '{role}'. Allowed: {sorted(allowed_subs)}"
                )


def _validate_linux(cmd: str, role: str) -> None:
    """Validate a Linux command for safety based on user role."""
    cmd = cmd.strip()
    # Length limit prevents overflow-style attacks
    if len(cmd) > settings.max_command_length:
        raise ValueError(
            f"Command too long ({len(cmd)} chars, max {settings.max_command_length})"
        )
    forbidden_re = FORBIDDEN_LINUX_WRITE_RE if role in ("admin", "superadmin") else FORBIDDEN_LINUX_RE
    if forbidden_re.search(cmd):
        raise ValueError("Shell metacharacters not allowed in Linux command")

    # Handle pipes: split by |, validate each side
    if "|" in cmd:
        parts = cmd.split("|")
        if len(parts) > 2:
            raise ValueError("Only one pipe allowed")
        left_tokens = parts[0].strip().split()
        right_tokens = parts[1].strip().split()
        if not right_tokens:
            raise ValueError("Empty right side of pipe")

        _validate_linux_command(left_tokens, role)
        if right_tokens[0] not in PIPE_SAFE_COMMANDS:
            raise ValueError(f"Pipe to '{right_tokens[0]}' not allowed. Allowed: {sorted(PIPE_SAFE_COMMANDS)}")
        return

    _validate_linux_command(cmd.split(), role)


@tool
def linux_exec(command: str) -> str:
    """Execute a Linux system command on the target server.

    Use this for system diagnostics: process list, disk space, memory usage,
    network info, service status, system logs, Docker status, etc.

    Common examples:
      ps aux | grep nginx
      df -h
      free -m
      ss -tlnp
      ip addr
      systemctl status docker
      journalctl -u kubelet --since '10 minutes ago' -n 50
      docker ps -a
      docker logs container-name --tail 50
      ls -la /var/log
      cat /proc/cpuinfo | grep model
      dmesg | tail -30
      uptime
      uname -a
      lsof -i :8080

    Args:
        command: The Linux command to execute (no kubectl prefix).

    Returns:
        The command output or error message.
    """
    role = _current_role.get()
    _validate_linux(command, role)
    return _ssh_exec(command)


# ============================================================
# Prometheus query
# ============================================================

def prometheus_query(query: str) -> str:
    """Query Prometheus for metrics data.

    Use PromQL to fetch cluster metrics. Common queries:
      rate(container_cpu_usage_seconds_total[5m])    — CPU usage rate
      container_memory_working_set_bytes             — Memory working set
      kube_deployment_status_replicas_available      — Available replicas
      up                                              — Target health

    Args:
        query: A PromQL query string.

    Returns:
        JSON formatted metric results, or error message.
    """
    import urllib.request
    import urllib.parse

    base_url = getattr(settings, 'prometheus_url', None)
    if not base_url:
        return "Prometheus not configured (set PROMETHEUS_URL env var)"

    encoded = urllib.parse.quote(query)
    url = f"{base_url.rstrip('/')}/api/v1/query?query={encoded}"

    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=settings.tool_exec_timeout)
        data = resp.read().decode("utf-8", errors="replace")
        return data
    except Exception as exc:
        return f"Prometheus query failed: {exc}"


# ============================================================
# Tool lists
# ============================================================

KUBECTL_TOOLS = [kubectl_exec]
LINUX_TOOLS = [linux_exec]
OPS_TOOLS = [kubectl_exec, linux_exec]
