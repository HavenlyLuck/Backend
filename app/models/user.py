from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"
    user_id           = Column(Integer, primary_key=True, autoincrement=True)
    login_id          = Column(String(50), unique=True, nullable=False)
    nickname          = Column(String(50), unique=True, nullable=False)
    email             = Column(String(100), unique=True, nullable=False)
    password          = Column(String(255), nullable=False)
    phone             = Column(String(20), unique=True, nullable=False)
    phone_verified_at = Column(DateTime, nullable=False)
    avatar_url        = Column(String(500), nullable=True)
    trade_count       = Column(Integer, default=0)
    is_admin          = Column(Boolean, default=False, nullable=False, server_default="0")
    created_at        = Column(DateTime, server_default=func.now())
    updated_at        = Column(DateTime, server_default=func.now(), onupdate=func.now())