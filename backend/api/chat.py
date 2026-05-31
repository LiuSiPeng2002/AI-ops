from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from database import get_db
from models.user import User
from schemas.chat import ChatRequest, ResumeRequest
from services.chat_service import chat_stream_generator, resume_chat_stream

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming endpoint for AI-Ops chat."""
    # Lookup machine credentials from DB (don't trust frontend)
    machine_config = None
    if request.machine_id:
        from models.machine import Machine
        result = await db.execute(select(Machine).where(Machine.id == request.machine_id))
        m = result.scalar_one_or_none()
        if m:
            machine_config = {
                "host": m.host, "port": m.port,
                "username": m.username, "password": m.password,
            }
    return StreamingResponse(
        chat_stream_generator(
            message=request.message,
            session_id=request.session_id,
            user_id=current_user.id,
            user_role=current_user.role,
            machine_config=machine_config,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/resume")
async def resume_stream(request: ResumeRequest, current_user: User = Depends(get_current_user)):
    """Resume a paused graph with approval decision. Returns SSE stream."""
    return StreamingResponse(
        resume_chat_stream(
            session_id=request.session_id,
            approved=request.approved,
            reason=request.reason,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
