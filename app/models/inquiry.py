from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class Inquiry(Base):
    __tablename__ = "inquiries"
    inquiry_id  = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title       = Column(String(200), nullable=False)
    content     = Column(Text, nullable=False)
    is_private  = Column(Boolean, default=False, nullable=False, server_default="0")   # 비공개 문의 여부
    answer      = Column(Text, nullable=True)                                      # 관리자 답변 (없으면 답변대기)
    admin_id    = Column(Integer, ForeignKey("users.user_id"), nullable=True)      # 답변한 관리자
    answered_at = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())
