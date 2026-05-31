"""Consolidation Agent — converts completed sessions into structured knowledge cases.

Runs asynchronously after a session ends. Uses LLM to extract:
  - Symptoms → root cause → failed attempts → successful approach → verification
Stores as both MySQL record (knowledge_cases) and ChromaDB vector embedding.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from config import settings


async def consolidate_session(session_data: dict) -> dict | None:
    """Analyze a completed session and generate a knowledge case.

    Args:
        session_data: {session_id, intent_type, final_status, messages: [...], ...}

    Returns:
        The generated case dict, or None if the session isn't worth consolidating.
    """
    # Skip inquiry-only sessions (no fix performed)
    if session_data.get("intent_type") == "inquiry" and session_data.get("final_status") != "success":
        return None

    # Skip sessions with too few messages
    messages = session_data.get("messages", [])
    if len(messages) < 3:
        return None

    # Build context
    context = _build_context(session_data)

    # LLM extraction
    llm = ChatOpenAI(
        model=settings.model_name,
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_base_url,
        temperature=0.15,
        max_tokens=2000,
        timeout=settings.llm_request_timeout,
    )

    prompt = f"""You are an AI-Ops knowledge engineer. Analyze this diagnostic session and extract a structured knowledge case.

Session context:
{context[:5000]}

Output valid JSON (no markdown fences):
{{
  "title": "<one-line summary of the incident>",
  "symptoms": ["<symptom1>", "<symptom2>"],
  "root_cause": "<root cause analysis>",
  "solution": "<successful fix approach>",
  "severity": "critical|warning|info",
  "service_name": "<affected service>",
  "namespace": "<namespace>",
  "tags": ["<tag1>", "<tag2>"],
  "lessons_learned": "<what we learned from this incident>",
  "should_consolidate": true
}}

If this session is trivial (simple inquiry, no fix performed, no anomaly found), return:
{{ "should_consolidate": false }}
"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content or "{}"
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
        case = json.loads(raw)
        return case
    except Exception:
        # LLM may fail — don't block session completion
        return None


async def store_case(case: dict, session_id: str, db) -> str | None:
    """Store a consolidated case to MySQL + ChromaDB. Returns case_id."""
    if not case.get("should_consolidate", True):
        return None

    case_id = str(uuid.uuid4())

    # Store to MySQL
    try:
        from sqlalchemy import text

        await db.execute(
            text("""
                INSERT INTO knowledge_cases
                (id, title, symptoms, root_cause, solution, severity, tags,
                 service_name, namespace, total_attempts, verified, source_session_id, created_at)
                VALUES (:id, :title, :symptoms, :root_cause, :solution, :severity, :tags,
                 :service_name, :namespace, :total_attempts, :verified, :source_session_id, :created_at)
            """),
            {
                "id": case_id,
                "title": case.get("title", f"Case from {session_id[:8]}"),
                "symptoms": json.dumps(case.get("symptoms", []), ensure_ascii=False),
                "root_cause": case.get("root_cause", ""),
                "solution": case.get("solution", ""),
                "severity": case.get("severity", "info"),
                "tags": json.dumps(case.get("tags", []), ensure_ascii=False),
                "service_name": case.get("service_name", ""),
                "namespace": case.get("namespace", ""),
                "total_attempts": 1,
                "verified": True,
                "source_session_id": session_id,
                "created_at": datetime.now(timezone.utc),
            },
        )
        await db.commit()
    except Exception:
        # Table may not exist yet — non-blocking
        pass

    # Store to ChromaDB
    try:
        from agents.chroma_store import add_document

        content_for_embedding = (
            f"Title: {case.get('title', '')}\n"
            f"Symptoms: {', '.join(case.get('symptoms', []))}\n"
            f"Root Cause: {case.get('root_cause', '')}\n"
            f"Solution: {case.get('solution', '')}\n"
            f"Tags: {', '.join(case.get('tags', []))}"
        )

        add_document(
            doc_id=case_id,
            title=case.get("title", f"Case-{session_id[:8]}"),
            content=content_for_embedding,
            metadata={
                "source": "auto-consolidation",
                "session_id": session_id,
                "severity": case.get("severity", "info"),
                "service_name": case.get("service_name", ""),
                "tags": ",".join(case.get("tags", [])),
            },
        )
    except Exception:
        pass

    return case_id


def _build_context(session_data: dict) -> str:
    """Build a concise LLM prompt context from session data."""
    parts = [
        f"Session: {session_data.get('session_id', '')[:12]}",
        f"Intent: {session_data.get('intent_type', 'unknown')}",
        f"Final Status: {session_data.get('final_status', 'unknown')}",
    ]

    messages = session_data.get("messages", [])
    for m in messages:
        role = m.get("role", "?")
        msg_type = m.get("message_type", "")
        agent = m.get("agent_name", "")
        content = m.get("content", "")

        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False)
        content_str = str(content)[:800]

        header = f"[{role}"
        if agent:
            header += f"/{agent}"
        if msg_type:
            header += f"/{msg_type}"
        header += "]"

        parts.append(f"{header} {content_str}")

    return "\n".join(parts)


async def run_consolidation_async(session_id: str, session_data: dict, db) -> None:
    """Fire-and-forget consolidation after session completion."""
    try:
        case = await consolidate_session(session_data)
        if case and case.get("should_consolidate", True):
            await store_case(case, session_id, db)
    except Exception:
        pass  # Never let consolidation failure affect the user
