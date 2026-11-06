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
    # 응모 상품으로 전환된 뒤 모금 때 산 응모권을 취소한 사람 — 이 시각까지 상점 전환 응모권을 살 수 없다
    funding_banned_until = Column(DateTime, nullable=True)
    # 가입 동의 기록 (동의 받았다는 증거) — 필수 동의는 가입 시각, 후기 홍보(선택)는 동의·철회 시각
    terms_agreed_at               = Column(DateTime, nullable=True)
    age_14_confirmed_at           = Column(DateTime, nullable=True)
    review_marketing_agreed_at    = Column(DateTime, nullable=True)   # 지금 동의 중이면 값이 있다
    review_marketing_withdrawn_at = Column(DateTime, nullable=True)   # 마지막으로 철회한 시각
    # 회원 탈퇴 시각 — 탈퇴하면 이 행의 개인정보는 지우고(가명 처리) 결제·배송 기록과의 연결만 남긴다
    deleted_at        = Column(DateTime, nullable=True)
    created_at        = Column(DateTime, server_default=func.now())
    updated_at        = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 후기 홍보 활용에 지금 동의 중인지 (UserResponse에서 쓴다)
    @property
    def review_marketing_agreed(self) -> bool:
        return self.review_marketing_agreed_at is not None
