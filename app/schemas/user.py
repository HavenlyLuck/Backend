from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Literal

class UserSignup(BaseModel):
    login_id: str
    nickname: str
    email: EmailStr
    password: str
    phone: str
    phone_verified_at: datetime       # 본인인증 완료 시간


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

    class Config:
        from_attributes = True

class DuplCheckRequest(BaseModel):
    field: Literal["login_id", "nickname", "email"]  # 이 세 가지만 허용
    value: str

class DuplCheckResponse(BaseModel):
    available: bool   # True = 사용가능, False = 중복
    message: str
