from sqlalchemy import Column, Integer, String, Boolean, DateTime, text

from database import Base


class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)
    host = Column(String(128), nullable=False)
    port = Column(Integer, default=22)
    username = Column(String(64), default="root")
    password = Column(String(256), default="")
    description = Column(String(256), default="")
    is_default = Column(Boolean, default=False)
    online = Column(Boolean, default=False)
    last_check_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=text("(CURRENT_TIMESTAMP)"))
