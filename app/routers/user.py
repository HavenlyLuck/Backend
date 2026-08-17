from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserSignup, UserLogin, UserResponse, TokenResponse,
    RefreshRequest, RefreshResponse, DuplCheckRequest, DuplCheckResponse,
)
from app.core.security import hash_password, verify_password, create_token, decode_token

router = APIRouter()

# 회원가입
@router.post("/signup", response_model=UserResponse)
def signup(body: UserSignup, db: Session = Depends(get_db)):
    # 중복 확인
    if db.query(User).filter(User.login_id == body.login_id).first():
        raise HTTPException(status_code=400, detail="이미 사용중인 아이디입니다")
    if db.query(User).filter(User.nickname == body.nickname).first():
        raise HTTPException(status_code=400, detail="이미 사용중인 닉네임입니다")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="이미 사용중인 이메일입니다")
    if db.query(User).filter(User.phone == body.phone).first():
        raise HTTPException(status_code=400, detail="이미 사용중인 전화번호입니다")

    user = User(
        login_id=body.login_id,
        nickname=body.nickname,
        email=body.email,
        password=hash_password(body.password),
        phone=body.phone,
        phone_verified_at=body.phone_verified_at
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# 로그인
@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, db: Session = Depends(get_db)):
    # DB에서 유저 찾기
    user = db.query(User).filter(User.login_id == body.login_id).first()

    # 유저 없거나 비밀번호 틀리면 에러
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")

    # JWT 액세스 토큰 + 리프레시 토큰 발급
    access_token = create_token({
        "sub": str(user.user_id),
        "type": "user",
        "is_admin": user.is_admin
    })
    refresh_token = create_token(
        {"sub": str(user.user_id), "type": "refresh"},
        expires_delta=settings.REFRESH_TOKEN_EXPIRE_MINUTES,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "is_admin": user.is_admin,
    }

# 액세스 토큰 재발급 (리프레시 토큰 이용)
@router.post("/refresh", response_model=RefreshResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다")

    user = db.query(User).filter(User.user_id == int(payload.get("sub"))).first()
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    access_token = create_token({
        "sub": str(user.user_id),
        "type": "user",
        "is_admin": user.is_admin
    })

    return {"access_token": access_token, "token_type": "bearer", "is_admin": user.is_admin}

# 회원가입 중복확인
@router.post("/duplCheck")
def dupl_check(body: DuplCheckRequest, db: Session = Depends(get_db)):
    if body.field == "login_id":
        exists = db.query(User).filter(User.login_id == body.value).first()
        label = "아이디"
    elif body.field == "nickname":
        exists = db.query(User).filter(User.nickname == body.value).first()
        label = "닉네임"
    elif body.field == "email":
        exists = db.query(User).filter(User.email == body.value).first()
        label = "이메일"

    if exists:
        return DuplCheckResponse(available=False, message=f"이미 사용중인 {label}입니다")
    return DuplCheckResponse(available=True, message=f"사용 가능한 {label}입니다")