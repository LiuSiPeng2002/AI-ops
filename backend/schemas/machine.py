from pydantic import BaseModel, Field


class MachineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    host: str
    port: int = 22
    username: str = "root"
    password: str = ""
    description: str = ""


class MachineUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    description: str | None = None
    is_default: bool | None = None
