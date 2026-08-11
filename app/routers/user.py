from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserSignup, UserLogin, UserResponse, TokenResponse, DuplCheckRequest, DuplCheckResponse
from app.core.security import hash_password, verify_password, create_token

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

    # JWT 토큰 발급
    token = create_token({
        "sub": str(user.user_id),
        "type": "user",
        "is_admin": user.is_admin
    })

    return {"access_token": token, "token_type": "bearer", "is_admin": user.is_admin}

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