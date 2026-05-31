import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.state import AIOpsState
from config import settings

ROUTER_PROMPT = """You are a K8s operations intent classifier. Analyze the user's input in context and classify it into exactly one type.

Types:
- "conversation": Pure greetings, small talk, or meta-questions about the conversation itself.
  Examples: "你好", "hello", "hi", "谢谢", "thanks", "我上一个问题是什么", "what was my last question", "你叫什么", "who are you"
  These do NOT need cluster data — route directly to final for a conversational reply.
- "diagnosis": The user is asking to investigate, troubleshoot, or diagnose a problem.
  Examples: "pod crashing", "service down", "排查", "为什么会这样", "检查集群状态"
- "change": The user is asking to perform an operation or change, OR approving a proposed action.
  Examples: "scale up", "restart", "扩容", "重启", "删除pod", "允许", "好的", "可以", "执行"
- "inquiry": The user is asking a specific technical question about cluster/K8s operations.
  Examples: "what nodes exist", "how does X work", "有哪些pods", "怎么部署"

CRITICAL: If the assistant's last message proposed an action and the user responds with approval words (允许/好的/可以/yes/ok/确认/执行/go ahead/sure/please do), classify as "change".

Also extract the target scope if mentioned: service name, namespace, node name, host name.

Respond ONLY with valid JSON:
{"intent_type": "conversation|diagnosis|change|inquiry", "target_scope": {"service": "...", "namespace": "default", "node": "..."}}
"""

FINAL_PROMPT = """You are an AI-Ops assistant. Synthesize the information collected by the other agents into a clear, actionable response.

Guidelines:
1. Summarize what was observed (metrics, events, logs)
2. If a root cause was identified, explain it clearly with evidence
3. If relevant knowledge base cases were found, reference them
4. Suggest next steps or remediation actions
5. If the user has admin or superadmin privileges, you may suggest and execute write operations (restart, scale, delete pods, etc.) directly
6. Reply in the same language as the user (Chinese → Chinese, English → English)
7. Be concise but thorough. Do not fabricate information not present in the agent outputs.

IMPORTANT — If you propose an action that requires user approval (e.g., "是否允许我执行...", "Should I run..."), you MUST append a PROPOSAL block at the very end. The PROPOSAL block must be the last thing in your response:

PROPOSAL:
ACTION: <one-line description of the proposed action>
COMMAND: <the exact shell command to execute, single line>
REASON: <why this action is needed>
END_PROPOSAL
"""

llm = ChatOpenAI(
    model=settings.model_name,
    openai_api_key=settings.openai_api_key,
    openai_api_base=settings.openai_base_url,
    temperature=0,
)


def _extract_reasoning(response) -> str:
    return response.additional_kwargs.get("reasoning_content", "")


async def orchestrator_router_node(state: AIOpsState) -> dict:
    """Classify user intent and extract target scope."""
    user_input = state["user_input"]
    messages = state.get("messages", [])
    pending_proposal = state.get("pending_proposal")

    chat_messages = [SystemMessage(content=ROUTER_PROMPT)]

    # Include recent conversation for context (last 2 exchanges)
    recent = messages[-4:] if len(messages) > 4 else messages
    for m in recent:
        role = m.get("role", "user")
        content = m.get("content", "")[:500]
        if role == "user":
            chat_messages.append(HumanMessage(content=content))
        else:
            chat_messages.append(SystemMessage(content=f"[Assistant previously said]: {content}"))

    # Add pending proposal context if present
    if pending_proposal and pending_proposal.get("action"):
        chat_messages.append(SystemMessage(content=(
            f"[Pending proposal from previous turn]: {pending_proposal.get('action')}\n"
            f"Reason: {pending_proposal.get('reason', '')}\n"
            f"If the user is approving this, classify as 'change'."
        )))

    chat_messages.append(HumanMessage(content=user_input))

    response = await llm.ainvoke(chat_messages)
    reasoning = _extract_reasoning(response)

    try:
        content = response.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        result = {"intent_type": "inquiry", "target_scope": {}}

    return {
        "intent_type": result.get("intent_type", "inquiry"),
        "target_scope": result.get("target_scope", {}),
        "current_agent": "orchestrator",
        "flow_stage": result.get("intent_type", "inquiry"),
        "remedy_needed": result.get("intent_type") in ("diagnosis", "change"),
        "retry_count": 0,
        "remedy_attempts": 0,
        "loop_complete": False,
        "reasoning_trace": [{"agent": "orchestrator", "content": reasoning}] if reasoning else [],
    }


async def orchestrator_final_node(state: AIOpsState) -> dict:
    """Synthesize all agent outputs into a final response."""
    user_input = state["user_input"]
    intent_type = state.get("intent_type", "inquiry")
    anomaly_summary = state.get("anomaly_summary", "")
    anomaly_severity = state.get("anomaly_severity", "")
    collected_data = state.get("collected_data", {})
    hypotheses = state.get("hypotheses", [])
    root_cause = state.get("confirmed_root_cause", {})
    rag_context = state.get("rag_context", "")
    tool_results = state.get("tool_results", [])

    context_parts = [f"## User Intent\n{user_input}\nType: {intent_type}"]

    # Include conversation history so LLM remembers previous turns
    messages = state.get("messages", [])
    if messages:
        context_parts.append("## Conversation History")
        for m in messages[-10:]:
            role_label = "User" if m.get("role") == "user" else "Assistant"
            context_parts.append(f"- [{role_label}]: {m.get('content', '')[:500]}")

    if anomaly_summary:
        context_parts.append(f"## Anomalies Detected (severity: {anomaly_severity})\n{anomaly_summary}")

    if tool_results:
        context_parts.append("## Tool Results")
        for tr in tool_results:
            context_parts.append(f"- [{tr['tool']}] {tr.get('result', '')[:500]}")

    if hypotheses:
        context_parts.append("## Hypotheses")
        for h in hypotheses:
            context_parts.append(f"- {h.get('hypothesis', '')} (confidence: {h.get('confidence', 0)})")

    if root_cause:
        context_parts.append(f"## Root Cause\n{root_cause.get('cause', '')} (confidence: {root_cause.get('confidence', 0)})")

    if rag_context:
        context_parts.append(f"## Related Knowledge\n{rag_context[:1000]}")

    # Remedy results
    remedy_results = state.get("remedy_results", [])
    if remedy_results:
        context_parts.append("## Remedy Actions")
        for rr in remedy_results:
            status = "SUCCESS" if rr.get("success") else "FAILED"
            context_parts.append(f"- [{status}] [Risk:{rr.get('risk_level','L0')}] {rr.get('command','')}: {rr.get('output','')[:300]}")

    # Verification
    verification = state.get("verification_results", {})
    if verification:
        context_parts.append(f"## Verification: {verification.get('overall', 'pending')}")
        for hc in verification.get("health_checks", []):
            context_parts.append(f"- {hc.get('check_type', '')}: {hc.get('status', 'unknown')}")

    retry_count = state.get("retry_count", 0)
    if retry_count > 0:
        context_parts.append(f"## Self-Healing Loop: {retry_count} retry attempt(s)")

    prompt = f"{FINAL_PROMPT}\n\n{'='.join(context_parts)}"

    chat_messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Generate the final diagnostic summary based on the above information."),
    ]

    response = await llm.ainvoke(chat_messages)
    reasoning = _extract_reasoning(response)

    full_response = response.content or ""

    # Extract PROPOSAL block if present
    pending_proposal = _parse_proposal(full_response)

    existing_messages = state.get("messages", [])
    trace = list(state.get("reasoning_trace", []))
    if reasoning:
        trace.append({"agent": "orchestrator_final", "content": reasoning})

    return {
        "final_response": full_response,
        "current_agent": "orchestrator_final",
        "flow_stage": "done",
        "pending_proposal": pending_proposal,
        "messages": existing_messages + [
            {"role": "user", "content": user_input},
            {"role": "agent", "content": full_response},
        ],
        "reasoning_trace": trace,
    }


def _parse_proposal(text: str) -> dict | None:
    """Parse PROPOSAL block from the final response text."""
    if "PROPOSAL:" not in text:
        return None
    try:
        proposal_text = text.split("PROPOSAL:")[1]
        if "END_PROPOSAL" in proposal_text:
            proposal_text = proposal_text.split("END_PROPOSAL")[0]
        result = {}
        for line in proposal_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("ACTION:"):
                result["action"] = line.split("ACTION:", 1)[1].strip()
            elif line.startswith("COMMAND:"):
                result["commands"] = [{"tool": "linux_exec", "command": line.split("COMMAND:", 1)[1].strip()}]
            elif line.startswith("REASON:"):
                result["reason"] = line.split("REASON:", 1)[1].strip()
        return result if result.get("action") else None
    except Exception:
        return None
