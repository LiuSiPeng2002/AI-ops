from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, JSON, ForeignKey, text

from database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(256), default="")
    intent_type = Column(Enum("diagnosis", "change", "inquiry"), default="inquiry")
    risk_level = Column(Enum("L0", "L1", "L2", "L3", "L4"), default="L0")
    status = Column(Enum("active", "completed", "escalated", "cancelled"), default="active")
    total_attempts = Column(Integer, default=0)
    final_status = Column(Enum("success", "partial_success", "failed", "escalated", "cancelled"))
    total_tokens = Column(Integer, default=0)
    duration_seconds = Column(Integer, default=0)
    started_at = Column(DateTime, server_default=text("(CURRENT_TIMESTAMP)"))
    ended_at = Column(DateTime, nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    role = Column(Enum("user", "agent", "system"), nullable=False)
    agent_name = Column(String(64), default="")
    message_type = Column(String(32), nullable=False)
    content = Column(JSON, nullable=False)
    token_count = Column(Integer, default=0)
    sequence_num = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=text("(CURRENT_TIMESTAMP(3))"))
