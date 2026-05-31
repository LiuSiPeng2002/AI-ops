import asyncio

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.state import AIOpsState
from agents.tools.ops_tools import OPS_TOOLS
from config import settings
from services.notification import notifier

OBSERVE_PROMPT = """You are the Observe Agent for K8s and Linux operations. Your job is to collect data about the cluster and system state.

## Tools
- **kubectl_exec**: Execute kubectl commands. Use for ANY K8s resource query.
  Examples: "get pods --all-namespaces", "get deployments -n default -o wide",
  "describe pod nginx", "top nodes", "get events -n default"
- **linux_exec**: Execute Linux system commands. Use for disk, memory, process,
  network, and service diagnostics.
  Examples: "df -h", "free -m", "ps aux | grep kube", "ss -tlnp",
  "systemctl status docker", "docker ps -a", "journalctl -u kubelet -n 50"

## Permissions
Your available commands depend on your role:
- **viewer/operator**: Read-only commands only (get, describe, logs, top, etc.)
- **admin**: Read + write commands (apply, delete, scale, restart, systemctl start/stop, etc.)
- **superadmin**: Full access including cluster administration

## Workflow
1. Use kubectl_exec for K8s cluster data, linux_exec for system diagnostics.
2. Match tools to user intent: pod issues→get pods + describe + logs, node issues→describe node,
   system issues→df + free + dmesg, network issues→ss + ip addr.
3. Collect enough data to enable diagnosis.

## Rules
- Generate SIMPLE, SINGLE commands. No ||, &&, 2>/dev/null, or shell constructs.
  Right: "systemctl status docker"  Wrong: "systemctl status docker 2>/dev/null || true"
  Right: "df -h"  Wrong: "df -h && du -sh /var/log"
- The tool will enforce permissions based on your role. If rejected, try a read-only alternative.
- Be thorough but efficient - don't collect unnecessary data.

## Output
After collecting data, output your findings as:
- ANOMALY_SUMMARY: Brief description of any issues found
- SEVERITY: critical / warning / info
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


async def observe_node(state: AIOpsState) -> dict:
    """Observe Agent: collect cluster data and detect anomalies."""
    user_input = state["user_input"]
    target = state.get("target_scope", {})

    prompt = f"{OBSERVE_PROMPT}\n\nUser request: {user_input}"
    if target:
        prompt += f"\nTarget scope: {target}"

    chat_messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=f"Collect relevant cluster data for: {user_input}"),
    ]

    response = await llm_with_tools.ainvoke(chat_messages)
    reasoning = _extract_reasoning(response)

    tool_results = []

    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_fn = next((t for t in OPS_TOOLS if t.name == tool_name), None)
            if tool_fn:
                try:
                    result = tool_fn.invoke(tool_args)
                    tool_results.append({"tool": tool_name, "args": tool_args, "result": str(result)})
                except Exception as e:
                    tool_results.append({"tool": tool_name, "args": tool_args, "result": f"Error: {e}"})

        # Second call to analyze collected data
        analysis_prompt = [SystemMessage(content=OBSERVE_PROMPT)]
        for tr in tool_results:
            analysis_prompt.append(HumanMessage(
                content=f"Tool [{tr['tool']}] with args {tr['args']} returned:\n{tr['result'][:1500]}"
            ))
        analysis_prompt.append(HumanMessage(
            content="Analyze the collected data. Output your findings in this format:\n"
                    "ANOMALY_SUMMARY: <brief description>\n"
                    "SEVERITY: <critical|warning|info>\n"
                    "If everything is normal, state that clearly."
        ))

        analysis_response = await llm.ainvoke(analysis_prompt)
        analysis_text = analysis_response.content
    else:
        analysis_text = response.content

    # Parse severity
    severity = "info"
    if "SEVERITY: critical" in analysis_text or "severity: critical" in analysis_text.lower():
        severity = "critical"
    elif "SEVERITY: warning" in analysis_text or "severity: warning" in analysis_text.lower():
        severity = "warning"

    trace = list(state.get("reasoning_trace", []))
    if reasoning:
        trace.append({"agent": "observe", "content": reasoning})

    # Fire DingTalk notification on critical/warning anomalies
    if severity in ("critical", "warning"):
        target = state.get("target_scope")
        asyncio.create_task(notifier.send_anomaly_alert(severity, analysis_text, target))

    return {
        "collected_data": {"tool_results": tool_results},
        "anomaly_summary": analysis_text,
        "anomaly_severity": severity,
        "tool_results": tool_results,
        "current_agent": "observe",
        "flow_stage": "diagnose",
        "reasoning_trace": trace,
    }
