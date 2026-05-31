"""Audit API: session history, message details, and SSE replay."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from database import get_db
from models.user import User
from services import audit as audit_service

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/sessions")
async def list_sessions(
    user_id: int | None = Query(None),
    intent_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List audit sessions. Non-admin users only see their own sessions."""
    # Enforce user isolation
    if current_user.role not in ("admin", "superadmin"):
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Cannot view other users' sessions")
        user_id = current_user.id

    items, total = await audit_service.list_sessions(
        db, user_id=user_id, intent_type=intent_type, status=status,
        limit=limit, offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a session detail. Non-admin can only access their own sessions."""
    data = await audit_service.get_session(db, session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    # Enforce user isolation
    if current_user.role not in ("admin", "superadmin") and data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot view other users' sessions")
    return data


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate audit statistics (admin only, or scoped to user)."""
    return await audit_service.get_session_stats(db)
