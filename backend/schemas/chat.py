from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    machine_id: int | None = None


class ResumeRequest(BaseModel):
    session_id: str
    approved: bool
    reason: str = ""


class SSEMessage(BaseModel):
    event: str
    data: dict
