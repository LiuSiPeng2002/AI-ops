from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.diagnose import diagnose_node
from agents.knowledge import knowledge_node
from agents.observe import observe_node
from agents.orchestrator import orchestrator_final_node, orchestrator_router_node
from agents.remedy import remedy_node
from agents.state import AIOpsState
from agents.verify import verify_node

_default_checkpointer = MemorySaver()


def _route_by_intent(state: AIOpsState) -> str:
    """Route to the appropriate agent based on intent type."""
    intent = state.get("intent_type", "inquiry")
    pending = state.get("pending_proposal")

    # Pure conversation — no cluster data needed
    if intent == "conversation":
        return "orchestrator_final"

    # Approval of pending proposal — skip observe, execute directly
    if intent == "change" and pending and pending.get("commands"):
        return "remedy"

    # Direct command execution (bash/kubectl/... in user input) — skip observe
    if intent == "change":
        user_input = state.get("user_input", "")
        direct_cmd_patterns = ["bash ", "sh ", "python3 ", "python ", "./", "kubectl ", "systemctl ", "docker "]
        if any(p in user_input for p in direct_cmd_patterns):
            return "remedy"

    return "observe"


# Track whether this is a direct command execution (skip verify)
_direct_execution: dict[str, bool] = {}

def _route_after_remedy(state: AIOpsState) -> str:
    """After remedy execution, decide: verify or skip to final.

    - Linux-only commands (bash, systemctl, docker, df, etc.): skip verify, go to final.
    - K8s commands (kubectl): verify is useful (check cluster state changed correctly).
    - Diagnosis repairs (not direct execution): always verify.
    """
    intent = state.get("intent_type", "")
    user_input = state.get("user_input", "")
    remedy_results = state.get("remedy_results", [])

    # If all remedy commands succeeded with no error, check whether it's Linux-only
    all_ok = all(r.get("success", True) for r in remedy_results) if remedy_results else True

    # Linux-only patterns: skip verify entirely
    linux_patterns = [
        "bash ", "sh ", "python3 ", "python ", "./",
        "systemctl ", "docker ", "df ", "free ", "ps ",
        "ls ", "cat ", "echo ", "mkdir ", "touch ", "chmod ", "chown ",
        "apt ", "yum ", "curl ", "wget ",
    ]
    is_linux_only = any(p in user_input for p in linux_patterns)

    # K8s patterns: verify is OK
    k8s_patterns = ["kubectl ", "get pods", "get nodes", "scale ", "delete pod", "apply "]
    is_k8s = any(p in user_input for p in k8s_patterns)

    if is_linux_only and not is_k8s and all_ok:
        return "orchestrator_final"

    # For diagnosis repairs (not direct execution), always verify
    if intent == "diagnosis":
        return "verify"

    # K8s direct execution: light verify
    return "verify"


def _route_after_observe(state: AIOpsState) -> str:
    """After data collection, route based on intent type."""
    intent = state.get("intent_type", "inquiry")
    if intent == "diagnosis":
        return "diagnose"
    if intent == "change":
        return "remedy"
    if intent == "inquiry":
        return "knowledge"
    return "orchestrator_final"


def _route_after_diagnose(state: AIOpsState) -> str:
    """After diagnosis: go to remedy if root cause found, else final."""
    root_cause = state.get("confirmed_root_cause", {})
    remedy_needed = state.get("remedy_needed", False)
    if remedy_needed and root_cause and root_cause.get("cause"):
        return "remedy"
    return "orchestrator_final"


def _route_after_verify(state: AIOpsState) -> str:
    """After verification: retry if failed and under max attempts, else final."""
    if state.get("loop_complete"):
        return "orchestrator_final"

    verification_passed = state.get("verification_passed", False)
    retry_count = state.get("retry_count", 0)
    max_retries = 2  # 3 total attempts (0, 1, 2)

    if not verification_passed and retry_count <= max_retries:
        return "remedy"
    return "orchestrator_final"


def build_graph(checkpointer=None) -> StateGraph:
    """Build the multi-agent AI-Ops LangGraph with conditional routing.

    Graph flow:
      orchestrator -> observe -> diagnose -> remedy -> verify
                      |            |          ^          |
                      v            v          |          v
                  knowledge    orchestrator_final <-- orchestrator_final -> END
    """
    workflow = StateGraph(AIOpsState)

    # Register all agent nodes
    workflow.add_node("orchestrator", orchestrator_router_node)
    workflow.add_node("observe", observe_node)
    workflow.add_node("diagnose", diagnose_node)
    workflow.add_node("knowledge", knowledge_node)
    workflow.add_node("remedy", remedy_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("orchestrator_final", orchestrator_final_node)

    # Entry point
    workflow.set_entry_point("orchestrator")

    # orchestrator -> observe (most) / remedy (approval) / final (conversation)
    workflow.add_conditional_edges(
        "orchestrator",
        _route_by_intent,
        {"observe": "observe", "remedy": "remedy", "orchestrator_final": "orchestrator_final"},
    )

    # observe -> diagnose / remedy / knowledge / orchestrator_final
    workflow.add_conditional_edges(
        "observe",
        _route_after_observe,
        {
            "diagnose": "diagnose",
            "remedy": "remedy",
            "knowledge": "knowledge",
            "orchestrator_final": "orchestrator_final",
        },
    )

    # diagnose -> remedy / orchestrator_final
    workflow.add_conditional_edges(
        "diagnose",
        _route_after_diagnose,
        {
            "remedy": "remedy",
            "orchestrator_final": "orchestrator_final",
        },
    )

    # remedy -> verify
    # remedy → verify (repair) or orchestrator_final (direct command execution)
    workflow.add_conditional_edges(
        "remedy",
        _route_after_remedy,
        {"verify": "verify", "orchestrator_final": "orchestrator_final"},
    )

    # verify -> retry (remedy) or final
    workflow.add_conditional_edges(
        "verify",
        _route_after_verify,
        {
            "remedy": "remedy",
            "orchestrator_final": "orchestrator_final",
        },
    )

    # knowledge -> orchestrator_final -> END
    workflow.add_edge("knowledge", "orchestrator_final")
    workflow.add_edge("orchestrator_final", END)

    return workflow.compile(checkpointer=checkpointer or _default_checkpointer)
