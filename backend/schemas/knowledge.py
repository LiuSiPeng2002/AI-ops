from pydantic import BaseModel, Field


class KnowledgeUploadRequest(BaseModel):
    title: str = ""
    content: str
    source: str = "manual"
    tags: list[str] = []


class KnowledgeSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)


class AutoGenerateRequest(BaseModel):
    session_id: str
