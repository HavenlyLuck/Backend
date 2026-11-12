from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Literal, Optional

class UserSignup(BaseModel):
    login_id: str
    nickname: str
    email: EmailStr
    password: str
    identity_verification_id: str     # 포트원 본인인증 ID (이름·전화번호·인증시간은 서버가 포트원에서 직접 조회)
    referral_code: Optional[str] = None   # 추천인 코드 (선택)
    # 가입 동의 — 필수 둘은 true여야 가입된다. 동의 시각은 서버가 기록한다
    terms_agreed: bool = False             # (필수) 이용약관 동의
    age_14_confirmed: bool = False         # (필수) 만 14세 이상 확인
    review_marketing_agreed: bool = False  # (선택) 후기 SNS·홈페이지 홍보 활용 동의


class IdentityVerifyRequest(BaseModel):   # 본인인증 결과 확인 요청
    identity_verification_id: str

class IdentityVerifyResponse(BaseModel):  # 본인인증 결과 (가입 폼에 보여줄 값)
    name: Optional[str] = None
    phone: str


class WithdrawRequest(BaseModel):         # 회원 탈퇴 요청 (본인 확인용 비밀번호)
    password: str


class ReviewMarketingConsentRequest(BaseModel):   # 후기 홍보 활용 동의·철회
    agreed: bool


class PasswordChangeRequest(BaseModel):   # 비밀번호 변경 요청 (마이페이지 설정)
    current_password: str
    new_password: str


class UserLogin(BaseModel):        # 로그인 요청
    login_id: str
    password: str

class TokenResponse(BaseModel):    # 로그인 응답 (토큰 반환)
    access_token: str
    refresh_token: str
    token_type: str
    is_admin: bool

class RefreshRequest(BaseModel):   # 토큰 재발급 요청
    refresh_token: str

class RefreshResponse(BaseModel):  # 토큰 재발급 응답
    access_token: str
    token_type: str
    is_admin: bool

class UserResponse(BaseModel):
    user_id: int
    login_id: str
    nickname: str
    email: str
    avatar_url: Optional[str] = None
    avatar_config: Optional[dict] = None
    trade_count: int
    review_marketing_agreed: bool = False   # 후기 SNS·홈페이지 홍보 활용에 지금 동의 중인지

    class Config:
        from_attributes = True

class DuplCheckRequest(BaseModel):
    field: Literal["login_id", "nickname", "email", "phone"]  # 이 네 가지만 허용
    value: str

class DuplCheckResponse(BaseModel):
    available: bool   # True = 사용가능, False = 중복
    message: str


class FindIdRequest(BaseModel):            # 아이디 찾기 (본인인증만으로)
    identity_verification_id: str

class FindIdResponse(BaseModel):
    login_id: str
    joined_at: Optional[datetime] = None   # 가입일 (내 계정이 맞는지 확인용)

class PasswordResetCheckRequest(BaseModel):   # 비밀번호 찾기 1단계: 아이디와 본인인증한 사람이 같은지
    login_id: str
    identity_verification_id: str

class PasswordResetRequest(BaseModel):        # 비밀번호 찾기 2단계: 새 비밀번호 설정
    login_id: str
    identity_verification_id: str
    new_password: str
