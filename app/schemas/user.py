from pydantic import BaseModel, EmailStr
from typing import Literal, Optional

class UserSignup(BaseModel):
    login_id: str
    nickname: str
    email: EmailStr
    password: str
    identity_verification_id: str     # 포트원 본인인증 ID (전화번호·인증시간은 서버가 포트원에서 직접 조회)


class IdentityVerifyRequest(BaseModel):   # 본인인증 결과 확인 요청
    identity_verification_id: str

class IdentityVerifyResponse(BaseModel):  # 본인인증 결과 (가입 폼에 보여줄 값)
    name: Optional[str] = None
    phone: str


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

    class Config:
        from_attributes = True

class DuplCheckRequest(BaseModel):
    field: Literal["login_id", "nickname", "email"]  # 이 세 가지만 허용
    value: str

class DuplCheckResponse(BaseModel):
    available: bool   # True = 사용가능, False = 중복
    message: str
