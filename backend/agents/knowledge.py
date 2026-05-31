from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.state import AIOpsState
from agents.tools.knowledge import search_knowledge_base
from config import settings

KNOWLEDGE_PROMPT = """You are the Knowledge Agent for K8s operations. Your job is to retrieve relevant information from the knowledge base.

## Workflow
1. Analyze the user's query to extract key search terms.
2. Use the search_knowledge_base tool to find relevant documents.
3. Summarize the retrieved information and explain how it applies to the user's question.

## Rules
- Search with concise, keyword-focused queries for best results.
- If no relevant documents are found, say so honestly.
- Cite which document the information came from.
- Answer in the same language as the user.
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


async def knowledge_node(state: AIOpsState) -> dict:
    """Knowledge Agent: RAG retrieval and knowledge base querying."""
    user_input = state["user_input"]

    chat_messages = [
        SystemMessage(content=KNOWLEDGE_PROMPT),
        HumanMessage(content=f"Find relevant knowledge for: {user_input}"),
    ]

    response = await llm_with_kb.ainvoke(chat_messages)
    reasoning = _extract_reasoning(response)

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

    # If no tool calls were made, try direct search based on user input
    if not rag_context:
        try:
            rag_context = search_knowledge_base.invoke({"query": user_input})
        except Exception:
            rag_context = ""

    trace = list(state.get("reasoning_trace", []))
    if reasoning:
        trace.append({"agent": "knowledge", "content": reasoning})

    response_text = response.content if response.content else ""

    return {
        "rag_context": rag_context,
        "current_agent": "knowledge",
        "flow_stage": "done",
        "final_response": response_text,
        "reasoning_trace": trace,
    }
