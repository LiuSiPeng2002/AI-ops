"""Remedy Agent: repair plan generation + execution + approval.

Generates a repair plan based on Diagnose Agent's root cause analysis,
risk-classifies each command, requests approval for L2+ operations,
executes approved commands via kubectl_exec/linux_exec, and collects results.
"""

import asyncio

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from agents.state import AIOpsState
from agents.tools.ops_tools import OPS_TOOLS
from agents.tools.risk_classifier import (
    classify_ops_risk,
    get_required_approver,
    is_auto_approved,
)
from config import settings
from services.notification import notifier

REMEDY_PROMPT = """You are the Remedy Agent for K8s and Linux operations. Your job is to generate and execute repair plans.

## Workflow
1. Review the root cause analysis from the Diagnose Agent.
2. Generate a step-by-step repair plan with specific commands.
3. Each command should use kubectl_exec (K8s operations) or linux_exec (system operations).
4. Execute the commands in order. Each command must be SIMPLE and SINGLE.

## Tools
- **kubectl_exec**: Execute kubectl commands. For ALL K8s operations.
  - Diagnosis: "get pods -n <ns>", "describe pod <name>", "logs <pod> --tail=100"
  - Repair: "delete pod <name> -n <ns>", "scale deployment <name> --replicas=N -n <ns>",
    "rollout restart deployment <name> -n <ns>", "apply -f <file>",
    "patch deployment <name> -n <ns> --patch '...'"
- **linux_exec**: Execute Linux system commands.
  - Diagnosis: "df -h", "free -m", "ss -tlnp", "systemctl status docker"
  - Repair: "systemctl restart docker", "systemctl start nginx",
    "docker restart <container>", "kill <pid>"

## Command Rules
- Generate SIMPLE, SINGLE commands. No ||, &&, 2>/dev/null, or shell constructs.
  Right: "delete pod payment-abc -n default"
  Wrong: "delete pod payment-abc && scale deployment payment --replicas=3"
- The tool will enforce permissions. If a command is rejected, try a safer alternative.
- For restart operations, prefer "rollout restart deployment" over "delete pod".
- For changing replica counts: use "kubectl_exec: scale deployment <name> --replicas=N".
  NEVER use sed/perl/python to edit YAML files for replica changes — it's fragile.
  Only edit YAML files when full-file changes are needed (e.g., adding volumes/env).
- Before using sed: first read the file, verify the target pattern EXISTS,
  then apply sed. After sed, re-read to confirm the change took effect.
- If sed finds no match (exit 0 but file unchanged), try a different approach.
- To RUN a script: ALWAYS use "bash /path/to/script.sh" or "python3 /path/to/script.py".
  NEVER try to execute scripts by direct path (e.g. "/root/hello.sh") — it will be rejected.
  The ONLY valid ways to execute scripts are: "bash <script>" or "sh <script>".
- To verify a script runs correctly: use "bash /path/to/script.sh" and check the output.
- NEVER generate duplicate commands. Each command must be unique.
  If you need to delete a file: ONE "rm /path/to/file" command. That's it. No follow-up ls, no second rm.
  If you need to restart a service: ONE "systemctl restart X" command. That's it.
  If the operation is simple (rm, touch, echo, chmod), just ONE command. No verification commands.
  Verification is handled by the Verify Agent separately.

## Output Format
Before executing, output your plan:
PLAN: <one-line strategy description>
COMMANDS:
  - kubectl_exec: <command>
  - linux_exec: <command>
"""

llm = ChatOpenAI(
    model=settings.model_name,
    openai_api_key=settings.openai_api_key,
    openai_api_base=settings.openai_base_url,
    temperature=0.2,
)
llm_with_tools = llm.bind_tools(OPS_TOOLS)


def _extract_reasoning(response) -> str:
    return response.additional_kwargs.get("reasoning_content", "")


def _parse_commands(text: str) -> list[dict]:
    """Parse commands from LLM output. Returns [{tool, args: {command}}]."""
    commands = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("- kubectl_exec:"):
            cmd = line.split("kubectl_exec:", 1)[1].strip()
            commands.append({"tool": "kubectl_exec", "args": {"command": cmd}})
        elif line.startswith("- linux_exec:"):
            cmd = line.split("linux_exec:", 1)[1].strip()
            commands.append({"tool": "linux_exec", "args": {"command": cmd}})
    return commands


async def remedy_node(state: AIOpsState) -> dict:
    """Remedy Agent: generate repair plan, check risk, approve, execute."""
    user_input = state["user_input"]
    root_cause = state.get("confirmed_root_cause", {})
    anomaly_summary = state.get("anomaly_summary", "")
    target = state.get("target_scope", {})
    user_role = state.get("user_role", "viewer")
    remedy_attempts = state.get("remedy_attempts", 0)
    retry_count = state.get("retry_count", 0)
    pending_proposal = state.get("pending_proposal")

    # Build context for the LLM
    context_parts = [f"## User Request\n{user_input}"]
    if target:
        context_parts.append(f"## Target Scope\n{target}")
    if anomaly_summary:
        context_parts.append(f"## Anomaly\n{anomaly_summary[:500]}")
    if root_cause:
        context_parts.append(f"## Root Cause\n{root_cause.get('cause', '')} (confidence: {root_cause.get('confidence', 0)})")

    # If this is a retry, add past failure context
    if remedy_attempts > 0:
        context_parts.append(f"\n## Previous Attempt ({remedy_attempts}) FAILED")
        context_parts.append("Analyze WHY the previous attempt failed and devise a DIFFERENT strategy.")
        if root_cause.get("failed_strategy"):
            context_parts.append(f"Previous failed strategy: {root_cause.get('failed_strategy')}")

    prompt = f"{REMEDY_PROMPT}\n\n{'  '.join(context_parts)}"

    # If user is approving a pending proposal, use its commands directly (no LLM call needed)
    if pending_proposal and pending_proposal.get("commands") and remedy_attempts == 0:
        all_commands = pending_proposal["commands"]
        plan_strategy = pending_proposal.get("action", "")
        reasoning = ""
    else:
        # Step 1: Generate repair plan via LLM
        chat_messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Generate a repair plan with specific commands. First output PLAN: and COMMANDS:, then execute them."),
        ]

        response = await llm_with_tools.ainvoke(chat_messages)
        reasoning = _extract_reasoning(response)
        content = response.content or ""

        # Parse plan and commands from LLM output
        plan_strategy = ""
        if "PLAN:" in content:
            plan_strategy = content.split("PLAN:", 1)[1].split("\n")[0].strip()

        parsed_commands = _parse_commands(content)

        # If LLM also generated tool_calls directly, use those too
        llm_tool_calls = []
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                llm_tool_calls.append({"tool": tc["name"], "args": tc["args"]})

        all_commands = parsed_commands + llm_tool_calls

        # Dedup: remove duplicate commands (same tool + same args)
        seen = set()
        deduped = []
        for c in all_commands:
            sig = (c["tool"], c["args"].get("command", ""))
            if sig not in seen:
                seen.add(sig)
                deduped.append(c)
        all_commands = deduped

        if not all_commands:
            # No commands generated — try to infer from the target + anomaly
            all_commands = _generate_fallback_commands(target, anomaly_summary)

    # Step 2: Risk-classify each command
    for cmd in all_commands:
        cmd["risk_level"] = classify_ops_risk(cmd["tool"], cmd["args"])

    max_risk = "L0"
    for cmd in all_commands:
        if int(cmd["risk_level"][1]) > int(max_risk[1]):
            max_risk = cmd["risk_level"]

    # Step 3: Check if approval is needed
    needs_approval_commands = [
        c for c in all_commands if not is_auto_approved(c["risk_level"], user_role)
    ]

    if needs_approval_commands and max_risk != "L0":
        # Pause graph for Human-in-the-Loop approval
        approval_data = interrupt({
            "type": "approval_required",
            "risk_level": max_risk,
            "required_approver": get_required_approver(max_risk),
            "commands": [
                {"tool": c["tool"], "command": c["args"].get("command", ""), "risk_level": c["risk_level"]}
                for c in needs_approval_commands
            ],
            "reason": plan_strategy or "Repair plan requires approval",
        })

        # Graph resumes here after Command(resume=...)
        if isinstance(approval_data, dict) and not approval_data.get("approved"):
            return {
                "remedy_results": [
                    {"command": "approval_required", "success": False, "output": "Rejected by user", "attempt": remedy_attempts}
                ],
                "loop_complete": True,
                "remedy_attempts": remedy_attempts,
                "current_agent": "remedy",
                "flow_stage": "remedy",
                "remedy_plan": {"strategy": plan_strategy, "commands": all_commands},
            }

    # Step 4: Execute all commands
    results = []
    for i, cmd in enumerate(all_commands):
        tool_name = cmd["tool"]
        tool_args = cmd["args"]
        tool_fn = next((t for t in OPS_TOOLS if t.name == tool_name), None)

        if not tool_fn:
            results.append({"command": f"{tool_name}({tool_args})", "success": False, "output": f"Tool {tool_name} not found", "attempt": remedy_attempts, "risk_level": cmd.get("risk_level", "L0")})
            continue

        try:
            result = tool_fn.invoke(tool_args)
            result_str = str(result)
            success = not result_str.lower().startswith("error")
            results.append({"command": f"{tool_name}({tool_args.get('command', '')})", "success": success, "output": result_str[:1000], "attempt": remedy_attempts, "risk_level": cmd.get("risk_level", "L0")})
        except Exception as e:
            results.append({"command": f"{tool_name}({tool_args.get('command', '')})", "success": False, "output": str(e)[:500], "attempt": remedy_attempts, "risk_level": cmd.get("risk_level", "L0")})

    # Step 5: Check if overall success
    all_success = all(r["success"] for r in results)

    # Fire DingTalk notification for remedy execution
    asyncio.create_task(notifier.send_remedy_alert(plan_strategy, results))

    trace = list(state.get("reasoning_trace", []))
    if reasoning:
        trace.append({"agent": "remedy", "content": reasoning})

    # Record failed strategy for retry context
    if not all_success and root_cause:
        root_cause["failed_strategy"] = plan_strategy

    return {
        "remedy_plan": {"strategy": plan_strategy, "commands": all_commands},
        "remedy_results": results,
        "remedy_attempts": remedy_attempts + 1,
        "loop_complete": all_success and remedy_attempts >= 0,
        "current_agent": "remedy",
        "flow_stage": "remedy",
        "reasoning_trace": trace,
        "confirmed_root_cause": root_cause,  # Pass back updated root_cause
        "pending_proposal": None,  # Clear the proposal after execution
    }


def _generate_fallback_commands(target: dict, anomaly_summary: str) -> list[dict]:
    """Generate fallback commands when LLM doesn't produce any."""
    commands = []
    service = target.get("service", "")
    namespace = target.get("namespace", "default")

    if service:
        commands.append({"tool": "kubectl_exec", "args": {"command": f"get pods -n {namespace} | grep {service}"}})
        commands.append({"tool": "kubectl_exec", "args": {"command": f"describe deployment {service} -n {namespace}"}})
        commands.append({"tool": "kubectl_exec", "args": {"command": f"get events -n {namespace} --sort-by='.lastTimestamp'"}})

    if "crashloop" in anomaly_summary.lower() or "oom" in anomaly_summary.lower():
        if service:
            commands.append({"tool": "kubectl_exec", "args": {"command": f"rollout restart deployment {service} -n {namespace}"}})
    elif "pending" in anomaly_summary.lower():
        commands.append({"tool": "linux_exec", "args": {"command": "df -h"}})
        commands.append({"tool": "linux_exec", "args": {"command": "free -m"}})

    return commands
