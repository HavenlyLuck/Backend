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
    # 본인인증 CI — 사람마다 하나뿐이고 번호를 바꿔도 그대로라, 아이디·비밀번호 찾기에서 본인 확인에 쓴다. 예전 가입자는 비어 있음
    ci                = Column(String(100), unique=True, nullable=True)
    avatar_url        = Column(String(500), nullable=True)
    avatar_config     = Column(JSON, nullable=True)   # 픽셀 캐릭터 커스터마이징 (app/schemas/avatar.py)
    trade_count       = Column(Integer, default=0)
    is_admin          = Column(Boolean, default=False, nullable=False, server_default="0")
    # 관리자 2단계 인증(OTP 앱) — 비밀키는 암호화해서 둔다(app/core/totp.py). 설정 중이면 enabled_at이 비어 있다.
    # last_step: 마지막으로 쓴 OTP의 30초 구간 번호 — 같은 코드를 두 번 쓰지 못하게 한다
    totp_secret       = Column(String(255), nullable=True)
    totp_enabled_at   = Column(DateTime, nullable=True)
    totp_last_step    = Column(Integer, nullable=True)
    # 추천인 — 내 고유 코드, 나를 추천한 사람(한 번만 등록), 첫 응모권 구매로 추천 보상을 받은 시각
    referral_code        = Column(String(12), unique=True, nullable=True)
    referred_by_user_id  = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    referral_rewarded_at = Column(DateTime, nullable=True)
    # 응모 상품으로 전환된 뒤 모금 때 산 응모권을 취소한 사람 — 이 시각까지 상점 전환 응모권을 살 수 없다
    funding_banned_until = Column(DateTime, nullable=True)
    # 가입 동의 기록 (동의 받았다는 증거) — 필수 동의는 가입 시각, 후기 홍보(선택)는 동의·철회 시각
    terms_agreed_at               = Column(DateTime, nullable=True)
    age_14_confirmed_at           = Column(DateTime, nullable=True)
    # 만 19세 미만 가입자의 법정대리인(보호자) 동의 기록 — 보호자 본인인증으로 확인한 이름·번호·CI와 동의 시각.
    # 성인 가입자는 비어 있다
    guardian_name                 = Column(String(50), nullable=True)
    guardian_phone                = Column(String(20), nullable=True)
    guardian_ci                   = Column(String(100), nullable=True)
    guardian_consented_at         = Column(DateTime, nullable=True)
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


class UsedIdentityVerification(Base):
    """한 번 쓴 본인인증 ID — 같은 인증으로 비밀번호를 두 번 바꾸지 못하게 기록한다"""
    __tablename__ = "used_identity_verifications"
    identity_verification_id = Column(String(64), primary_key=True)
    purpose                  = Column(String(30), nullable=False)   # password_reset / guardian_consent
    used_at                  = Column(DateTime, server_default=func.now(), nullable=False)
