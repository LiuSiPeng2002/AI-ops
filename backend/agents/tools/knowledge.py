from langchain_core.tools import tool

from agents.chroma_store import search as chroma_search


@tool
def search_knowledge_base(query: str) -> str:
    """Search the K8s operations knowledge base for relevant troubleshooting guides, runbooks, and historical cases.

    Args:
        query: A natural language query describing the issue or topic to search for.

    Returns:
        Formatted text of the most relevant knowledge base entries.
    """
    results = chroma_search(query, k=3)
    if not results:
        return "No relevant documents found in the knowledge base."

    lines = []
    for i, doc in enumerate(results, 1):
        title = doc.get("metadata", {}).get("title", "Untitled")
        dist = doc.get("distance", 0)
        lines.append(f"[{i}] {title} (relevance: {1 - dist:.2f})")
        lines.append(doc.get("content", ""))
        lines.append("---")
    return "\n".join(lines)
