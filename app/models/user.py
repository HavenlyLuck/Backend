from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"
    user_id           = Column(Integer, primary_key=True, autoincrement=True)
    login_id          = Column(String(50), unique=True, nullable=False)
    nickname          = Column(String(50), unique=True, nullable=False)
    email             = Column(String(100), unique=True, nullable=False)
    password          = Column(String(255), nullable=False)
    name              = Column(String(50), nullable=True)    # 본인인증 실명 (결제창 구매자 이름). 예전 가입자는 비어 있음
    phone             = Column(String(20), unique=True, nullable=False)
    phone_verified_at = Column(DateTime, nullable=False)
    avatar_url        = Column(String(500), nullable=True)
    avatar_config     = Column(JSON, nullable=True)   # 픽셀 캐릭터 커스터마이징 (app/schemas/avatar.py)
    trade_count       = Column(Integer, default=0)
    is_admin          = Column(Boolean, default=False, nullable=False, server_default="0")
    # 추천인 — 내 고유 코드, 나를 추천한 사람(한 번만 등록), 첫 응모권 구매로 추천 보상을 받은 시각
    referral_code        = Column(String(12), unique=True, nullable=True)
    referred_by_user_id  = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    referral_rewarded_at = Column(DateTime, nullable=True)
    created_at        = Column(DateTime, server_default=func.now())
    updated_at        = Column(DateTime, server_default=func.now(), onupdate=func.now())