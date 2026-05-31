import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.state import AIOpsState
from agents.tools.knowledge import search_knowledge_base
from config import settings

DIAGNOSE_PROMPT = """You are the Diagnose Agent for K8s operations. Your job is root cause analysis.

## Workflow
1. Review the data collected by the Observe Agent.
2. Generate 2-3 diagnostic hypotheses, each with a confidence score (0-1) and supporting evidence.
3. Use the search_knowledge_base tool to find similar historical cases or relevant runbook documentation.
4. Select the most likely hypothesis as the confirmed root cause.

## Output Format
Respond with valid JSON:
{
  "hypotheses": [
    {"hypothesis": "...", "confidence": 0.85, "evidence": "..."}
  ],
  "confirmed_root_cause": {"cause": "...", "confidence": 0.92},
  "search_query": "query string for knowledge base"
}

## Rules
- Base your analysis ONLY on the collected data, not assumptions.
- If data is insufficient, say so rather than guessing.
- Consider the service dependency chain when analyzing impact.
- Set search_query to a concise search phrase for finding related cases.
"""

llm = ChatOpenAI(
    model=settings.model_name,
    openai_api_key=settings.openai_api_key,
    openai_api_base=settings.openai_base_url,
    temperature=0.3,
)
llm_with_kb = llm.bind_tools([search_knowledge_base])


def _extract_reasoning(response) -> str:
    return response.additional_kwargs.get("reasoning_content", "")


async def diagnose_node(state: AIOpsState) -> dict:
    """Diagnose Agent: root cause analysis with RAG."""
    anomaly_summary = state.get("anomaly_summary", "")
    anomaly_severity = state.get("anomaly_severity", "")
    tool_results = state.get("tool_results", [])
    user_input = state["user_input"]

    context = f"## User Request\n{user_input}\n\n## Observed Data\nSeverity: {anomaly_severity}\n{anomaly_summary}\n\n"
    if tool_results:
        context += "## Tool Results\n"
        for tr in tool_results:
            context += f"- [{tr['tool']}]: {tr.get('result', '')[:800]}\n"

    chat_messages = [
        SystemMessage(content=DIAGNOSE_PROMPT),
        HumanMessage(content=f"{context}\n\nGenerate hypotheses and root cause analysis."),
    ]

    response = await llm_with_kb.ainvoke(chat_messages)
    reasoning = _extract_reasoning(response)

    hypotheses = []
    root_cause = {}
    rag_context = ""

    # Handle tool calls for knowledge base search
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            if tc["name"] == "search_knowledge_base":
                try:
                    kb_result = search_knowledge_base.invoke(tc["args"])
                    rag_context = str(kb_result)
                except Exception as e:
                    rag_context = f"Knowledge search error: {e}"

    # Parse the LLM response for structured data
    content = response.content.strip()
    try:
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        parsed = json.loads(content)
        hypotheses = parsed.get("hypotheses", [])
        root_cause = parsed.get("confirmed_root_cause", {})
    except (json.JSONDecodeError, IndexError):
        hypotheses = [{"hypothesis": content[:200], "confidence": 0.5, "evidence": ""}]

    trace = list(state.get("reasoning_trace", []))
    if reasoning:
        trace.append({"agent": "diagnose", "content": reasoning})

    return {
        "hypotheses": hypotheses,
        "confirmed_root_cause": root_cause,
        "rag_context": rag_context,
        "current_agent": "diagnose",
        "flow_stage": "done",
        "reasoning_trace": trace,
    }
