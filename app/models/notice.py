from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class Notice(Base):
    __tablename__ = "notices"
    notice_id  = Column(Integer, primary_key=True, autoincrement=True)
    admin_id   = Column(Integer, ForeignKey("users.user_id"), nullable=False)   # 작성한 관리자
    title      = Column(String(200), nullable=False)
    content    = Column(Text, nullable=False)
    pinned     = Column(Boolean, default=False, nullable=False, server_default="0")   # 목록 맨 위 고정
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
