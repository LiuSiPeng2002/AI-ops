"""Knowledge base management API: upload, search, and auto-generate cases."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agents.chroma_store import add_document, delete_document, get_collection, search
from core.deps import get_current_user
from database import get_db
from models.session import Message, Session
from models.user import User
from schemas.knowledge import (
    AutoGenerateRequest,
    KnowledgeSearchRequest,
    KnowledgeUploadRequest,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/upload")
async def upload_knowledge(
    request: KnowledgeUploadRequest,
    current_user: User = Depends(get_current_user),
):
    """Manually upload a document to the knowledge base."""
    doc_id = str(uuid.uuid4())
    add_document(
        doc_id=doc_id,
        title=request.title,
        content=request.content,
        metadata={"source": request.source, "tags": ",".join(request.tags or [])},
    )
    return {"status": "ok", "document_id": doc_id}


@router.post("/search")
async def search_knowledge(
    request: KnowledgeSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """Search the knowledge base with semantic vector search."""
    results = search(request.query, k=request.limit)
    items = [
        {
            "id": r["id"],
            "content": r["content"][:500],
            "metadata": r.get("metadata", {}),
            "score": round(1 - r.get("distance", 0), 4) if r.get("distance") is not None else 0,
        }
        for r in results
    ]
    return {"query": request.query, "results": items, "total": len(items)}


@router.get("/list")
async def list_knowledge(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """List all documents in the knowledge base."""
    collection = get_collection()
    result = collection.get(limit=limit, offset=offset, include=["documents", "metadatas"])
    items = []
    for i, doc_id in enumerate(result.get("ids", [])):
        items.append({
            "id": doc_id,
            "content": (result["documents"][i] or "")[:300] if result.get("documents") else "",
            "metadata": result["metadatas"][i] if result.get("metadatas") else {},
        })
    return {"items": items, "total": len(result.get("ids", []))}


@router.delete("/{doc_id}")
async def delete_knowledge(
    doc_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a document from the knowledge base."""
    delete_document(doc_id)
    return {"status": "ok"}


@router.post("/auto-generate")
async def auto_generate_case(
    request: AutoGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Auto-generate a knowledge case from a completed session."""
    from sqlalchemy import select
    from config import settings
    from langchain_openai import ChatOpenAI

    session = await db.get(Session, request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all messages for this session
    messages = (await db.execute(
        select(Message).where(Message.session_id == request.session_id).order_by(Message.sequence_num)
    )).scalars().all()

    # Build context for LLM summarization
    parts = [f"## Session: {session.id}\nIntent: {session.intent_type}\nFinal: {session.final_status or 'unknown'}"]
    for m in messages:
        content_str = str(m.content)[:1000]
        parts.append(f"[{m.role}/{m.message_type}] {content_str}")

    context = "\n\n".join(parts)

    llm = ChatOpenAI(
        model=settings.model_name,
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_base_url,
        temperature=0.2,
    )

    prompt = f"""You are an AI-Ops knowledge engineer. Generate a concise, actionable knowledge base entry from this session.

Session context:
{context[:4000]}

Output format (plain text, no markdown headers):
TITLE: <one-line summary>
SYMPTOM: <what was observed>
ROOT_CAUSE: <what caused it>
SOLUTION: <step-by-step fix>
TAGS: <comma-separated keywords>
"""
    from langchain_core.messages import HumanMessage

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content or ""

    # Parse and store
    title = ""
    for line in content.split("\n"):
        if line.startswith("TITLE:"):
            title = line.split("TITLE:", 1)[1].strip()

    doc_id = str(uuid.uuid4())
    add_document(
        doc_id=doc_id,
        title=title or f"Case from {request.session_id[:8]}",
        content=content,
        metadata={
            "source": "auto-generated",
            "session_id": request.session_id,
            "intent_type": session.intent_type or "inquiry",
        },
    )
    return {"status": "ok", "document_id": doc_id, "title": title}
