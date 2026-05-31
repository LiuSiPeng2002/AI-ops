"""Deterministic L0-L4 risk classifier for kubectl/linux commands.

Maps command verbs and subcommands to risk levels based on the existing
RBAC permission sets from ops_tools.py.

Risk levels:
  L0 - Read-only (viewer+): get, describe, logs, top, df, ps, ss...
  L1 - Safe write (admin+): apply, create, label, touch, mkdir, cp...
  L2 - Destructive (admin+): delete, scale, restart, kill, rm...
  L3 - Dangerous (superadmin): exec, drain, port-forward, iptables...
  L4 - Catastrophic (superadmin): dd, fdisk, reboot, shutdown...
"""

from agents.tools.ops_tools import (
    ADMIN_KUBECTL_VERBS,
    ADMIN_LINUX_COMMANDS,
    ADMIN_SUBCOMMANDS,
    READONLY_KUBECTL_VERBS,
    SUPERADMIN_KUBECTL_VERBS,
    SUPERADMIN_LINUX_COMMANDS,
    SUPERADMIN_SUBCOMMANDS,
)

# ============================================================
# kubectl risk map
# ============================================================

READONLY_KUBECTL_RISK = {v: "L0" for v in READONLY_KUBECTL_VERBS}

# admin verbs — further split into L1 (safe write) vs L2 (destructive)
L1_KUBECTL_VERBS = {
    "apply", "create", "label", "annotate", "autoscale", "set",
}
L2_KUBECTL_VERBS = {
    "delete", "edit", "patch", "scale",
}

# superadmin verbs — L3 (dangerous but not irreversible)
L3_KUBECTL_VERBS = {
    "exec", "cp", "port-forward", "cordon", "uncordon", "taint", "certificate",
}
L4_KUBECTL_VERBS = {
    "drain",
}

# rollout subcommand risk
ROLLOUT_L1_SUB = {"pause", "resume"}
ROLLOUT_L2_SUB = {"restart", "undo"}
ROLLOUT_L0_SUB = {"status", "history"}


def classify_kubectl_risk(command: str) -> str:
    """Return L0-L4 risk level for a kubectl command string."""
    cmd = command.strip()
    parts = cmd.split()
    if not parts:
        return "L0"

    verb = parts[0]

    # rollout has per-subcommand risk
    if verb == "rollout":
        if len(parts) < 2:
            return "L0"
        sub = parts[1]
        if sub in ROLLOUT_L2_SUB:
            return "L2"
        if sub in ROLLOUT_L1_SUB:
            return "L1"
        return "L0"  # status, history

    if verb in L4_KUBECTL_VERBS:
        return "L4"
    if verb in L3_KUBECTL_VERBS:
        return "L3"
    if verb in L2_KUBECTL_VERBS:
        return "L2"
    if verb in L1_KUBECTL_VERBS:
        return "L1"
    return "L0"  # read-only verbs + unknown


# ============================================================
# Linux risk map
# ============================================================

# Read-only Linux commands are L0 — everything in LINUX_SAFE_COMMANDS
# that is NOT in ADMIN/SUPERADMIN is L0 by default.

# admin commands — split L1 vs L2
L1_LINUX_COMMANDS = {
    "touch", "mkdir", "cp", "ln", "tee",      # safe file ops
    "curl", "wget",                              # network fetch (safe direction)
    "apt", "apt-get", "yum", "dnf",             # package query/install
    "sed", "awk",                                # text processing (read-safe in pipe)
    "echo", "printf",                            # output (can redirect > to write)
}

L2_LINUX_COMMANDS = {
    "rm", "mv", "chmod", "chown", "kill", "killall",  # destructive
    "sysctl", "modprobe", "swapoff", "swapon",         # system state change
    "python3", "python", "bash",                         # arbitrary code execution
}

# superadmin — L3 vs L4
L3_LINUX_COMMANDS = {
    "iptables", "firewall-cmd", "ufw",  # network security
    "useradd", "usermod", "userdel",    # user management
    "passwd", "chpasswd",               # password
}

L4_LINUX_COMMANDS = {
    "dd", "fdisk", "mkfs", "parted",    # disk destruction
    "reboot", "shutdown", "init",       # system lifecycle
}

# Environment commands that are always L0
L0_LINUX_COMMANDS = {
    "ls", "cat", "head", "tail", "less", "find", "locate",
    "stat", "file", "md5sum", "sha256sum", "sha1sum",
    "df", "du", "mount", "lsblk", "blkid",
    "ps", "pstree", "top", "htop", "uptime",
    "free", "vmstat", "iostat", "mpstat",
    "dmesg", "uname", "hostname", "date", "who", "w", "last",
    "env", "printenv", "ulimit",
    "ip", "ifconfig", "ss", "netstat", "ping",
    "which", "whereis", "lsof", "lsmod", "lspci", "lsusb",
}

# Subcommand risk levels for multi-command tools
SYSTEMCTL_L0_SUB = {"status", "list-units", "list-unit-files", "is-active", "is-enabled", "show"}
SYSTEMCTL_L2_SUB = {"start", "stop", "restart", "reload"}
SYSTEMCTL_L3_SUB = {"enable", "disable", "mask", "unmask"}

DOCKER_L0_SUB = {"ps", "logs", "images", "inspect", "info", "version", "stats"}
DOCKER_L2_SUB = {"start", "stop", "restart", "pull", "build", "network", "volume"}
DOCKER_L3_SUB = {"exec", "rm"}
DOCKER_L4_SUB = {"rmi", "prune", "system"}

CRONTAB_L0_SUB = {"-l"}
CRONTAB_L2_SUB = {"-e"}


def classify_linux_risk(command: str) -> str:
    """Return L0-L4 risk level for a Linux command string."""
    cmd = command.strip()
    # Handle pipe: only check left side (the actual command)
    if "|" in cmd:
        cmd = cmd.split("|")[0].strip()

    parts = cmd.split()
    if not parts:
        return "L0"

    base = parts[0]

    # systemctl subcommand risk
    if base == "systemctl":
        if len(parts) < 2:
            return "L0"
        sub = parts[1]
        if sub in SYSTEMCTL_L3_SUB:
            return "L3"
        if sub in SYSTEMCTL_L2_SUB:
            return "L2"
        return "L0"

    # docker subcommand risk
    if base == "docker":
        if len(parts) < 2:
            return "L0"
        sub = parts[1]
        if sub in DOCKER_L4_SUB:
            return "L4"
        if sub in DOCKER_L3_SUB:
            return "L3"
        if sub in DOCKER_L2_SUB:
            return "L2"
        return "L0"

    # crontab subcommand risk
    if base == "crontab":
        if len(parts) < 2:
            return "L0"
        sub = parts[1]
        if sub in CRONTAB_L2_SUB:
            return "L2"
        return "L0"

    # mkfs.* variants (mkfs.ext4, mkfs.xfs, etc.)
    if base in L4_LINUX_COMMANDS or base.startswith("mkfs."):
        return "L4"
    if base in L3_LINUX_COMMANDS:
        return "L3"
    if base in L2_LINUX_COMMANDS:
        return "L2"
    if base in L1_LINUX_COMMANDS:
        return "L1"
    return "L0"


# ============================================================
# Unified classification + approval helpers
# ============================================================

def classify_ops_risk(tool_name: str, tool_args: dict) -> str:
    """Dispatch to kubectl or Linux classifier. Returns L0-L4."""
    command = tool_args.get("command", "")
    if tool_name == "kubectl_exec":
        return classify_kubectl_risk(command)
    if tool_name == "linux_exec":
        return classify_linux_risk(command)
    return "L0"


def is_auto_approved(risk_level: str, user_role: str) -> bool:
    """Check if a user role can auto-approve a given risk level.

    Auto-approval rules:
      L0-L1: all roles auto-approved
      L2:    admin+ auto-approved; viewer/operator need confirmation
      L3:    superadmin only auto-approved
      L4:    never auto-approved (always requires explicit confirmation)
    """
    if risk_level in ("L0", "L1"):
        return True
    if risk_level == "L2":
        return user_role in ("admin", "superadmin")
    if risk_level == "L3":
        return user_role == "superadmin"
    # L4: always needs approval
    return False


def get_required_approver(risk_level: str) -> str:
    """Return who needs to approve this risk level.
    L0-L1: none (auto), L2: user, L3: admin, L4: superadmin
    """
    if risk_level in ("L0", "L1"):
        return "none"
    if risk_level == "L2":
        return "user"
    if risk_level == "L3":
        return "admin"
    return "superadmin"
