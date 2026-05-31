"""Audit service: persist and query chat sessions and messages.

Session/Message models already exist in models/session.py but were never
wired up. This service provides the persistence and query layer.
"""

from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.session import Message, Session


async def create_session(
    db: AsyncSession,
    session_id: str,
    user_id: int,
    title: str = "",
    intent_type: str = "inquiry",
) -> Session:
    """Create a new audit session record."""
    s = Session(
        id=session_id,
        user_id=user_id,
        title=title,
        intent_type=intent_type,
        status="active",
        started_at=datetime.now(timezone.utc),
    )
    db.add(s)
    await db.commit()
    return s


async def update_session_status(
    db: AsyncSession,
    session_id: str,
    *,
    status: str | None = None,
    final_status: str | None = None,
    total_attempts: int | None = None,
    total_tokens: int | None = None,
    risk_level: str | None = None,
) -> None:
    """Update session fields after completion."""
    s = await db.get(Session, session_id)
    if not s:
        return
    if status is not None:
        s.status = status
    if final_status is not None:
        s.final_status = final_status
    if total_attempts is not None:
        s.total_attempts = total_attempts
    if total_tokens is not None:
        s.total_tokens = total_tokens
    if risk_level is not None:
        s.risk_level = risk_level
    s.ended_at = datetime.now(timezone.utc)
    await db.commit()


async def append_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    message_type: str,
    content: dict,
    agent_name: str = "",
    token_count: int = 0,
    sequence_num: int = 0,
) -> Message:
    """Append a message to an audit session."""
    m = Message(
        session_id=session_id,
        role=role,
        agent_name=agent_name,
        message_type=message_type,
        content=content,
        token_count=token_count,
        sequence_num=sequence_num,
    )
    db.add(m)
    await db.commit()
    return m


async def get_session(db: AsyncSession, session_id: str) -> dict | None:
    """Get a single session with its messages."""
    s = await db.get(Session, session_id)
    if not s:
        return None
    messages = (
        await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_num)
        )
    ).scalars().all()
    return {
        "id": s.id,
        "user_id": s.user_id,
        "title": s.title,
        "intent_type": s.intent_type,
        "risk_level": s.risk_level,
        "status": s.status,
        "final_status": s.final_status,
        "total_attempts": s.total_attempts,
        "total_tokens": s.total_tokens,
        "duration_seconds": s.duration_seconds,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "agent_name": m.agent_name,
                "message_type": m.message_type,
                "content": m.content,
                "sequence_num": m.sequence_num,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


async def list_sessions(
    db: AsyncSession,
    *,
    user_id: int | None = None,
    intent_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List sessions with optional filters. Returns (items, total)."""
    q = select(Session)
    if user_id:
        q = q.where(Session.user_id == user_id)
    if intent_type:
        q = q.where(Session.intent_type == intent_type)
    if status:
        q = q.where(Session.status == status)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0

    rows = (await db.execute(
        q.order_by(desc(Session.started_at)).offset(offset).limit(limit)
    )).scalars().all()

    items = []
    for s in rows:
        items.append({
            "id": s.id,
            "user_id": s.user_id,
            "title": s.title,
            "intent_type": s.intent_type,
            "risk_level": s.risk_level,
            "status": s.status,
            "final_status": s.final_status,
            "total_attempts": s.total_attempts,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        })
    return items, total


async def get_session_stats(db: AsyncSession) -> dict:
    """Get aggregate session statistics for the dashboard."""
    total = (await db.execute(select(func.count()).select_from(Session))).scalar() or 0
    active = (await db.execute(
        select(func.count()).where(Session.status == "active")
    )).scalar() or 0
    by_intent = {}
    rows = (await db.execute(
        select(Session.intent_type, func.count()).group_by(Session.intent_type)
    )).all()
    for intent, cnt in rows:
        by_intent[intent] = cnt
    return {
        "total_sessions": total,
        "active_sessions": active,
        "by_intent": by_intent,
    }
