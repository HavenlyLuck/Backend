from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base

# 유저가 구매한 아바타 아이템 (item_id는 app/core/avatar_items.py의 키)
class UserAvatarItem(Base):
    __tablename__ = "user_avatar_items"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_user_avatar_item"),)
    user_avatar_item_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id             = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    item_id             = Column(String(50), nullable=False)
    price               = Column(Integer, nullable=False)   # 구매 당시 가격
    purchased_at        = Column(DateTime, server_default=func.now())
