from sqlalchemy import Column, Integer, String, Enum, DateTime, text

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(Enum("viewer", "operator", "admin", "superadmin"), default="viewer", nullable=False)
    email = Column(String(128), default="")
    status = Column(Enum("active", "disabled"), default="active", nullable=False)
    created_at = Column(DateTime, server_default=text("(CURRENT_TIMESTAMP)"))
    updated_at = Column(DateTime, server_default=text("(CURRENT_TIMESTAMP)"), onupdate=text("CURRENT_TIMESTAMP"))
