import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional
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
    IdentityVerifyRequest, IdentityVerifyResponse, PasswordChangeRequest,
    WithdrawRequest, ReviewMarketingConsentRequest,
)
from app.core.security import hash_password, verify_password, create_token, decode_token
from app.core.dependencies import get_current_user
from app.crud import referral as referral_crud
from app.crud import withdrawal as withdrawal_crud
from app.schemas.avatar import AvatarConfig
from app.core.avatar_items import AVATAR_ITEM_SLOTS, OVERLAY_SLOTS, find_item_id
from app.crud import avatar_item as avatar_item_crud
from app.services.portone import get_verified_identity, PortOneError
from app.services.cloudinary import delete_image

router = APIRouter()

# 내 프로필 조회
@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user

# 내 캐릭터 저장 (설정 JSON만 저장하고, 이미지는 프론트에서 합성한다)
@router.put("/me/avatar", response_model=UserResponse)
def update_my_avatar(body: AvatarConfig, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.costume is not None and any(getattr(body, slot) is not None for slot in OVERLAY_SLOTS):
        raise HTTPException(status_code=400, detail="전체 스킨은 무기·모자·망토와 같이 착용할 수 없습니다")
    owned = avatar_item_crud.get_owned_item_ids(db, user.user_id)
    for slot in AVATAR_ITEM_SLOTS:
        index = getattr(body, slot)
        if index is None:
            continue
        item_id = find_item_id(slot, index)
        if item_id is None:
            raise HTTPException(status_code=400, detail="존재하지 않는 아이템입니다")
        if item_id not in owned:
            raise HTTPException(status_code=400, detail="보유하지 않은 아이템은 착용할 수 없습니다")
    user.avatar_config = body.model_dump(exclude_none=True)
    db.commit()
    db.refresh(user)
    return user

# 비밀번호 규칙 — 회원가입 화면(Frontend/app/signup)과 같다: 영문 대·소문자, 숫자, 특수문자 포함 8~20자
PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9\s]).{8,20}$")

# 내 비밀번호 변경 — 현재 비밀번호가 맞아야 바꿔 준다
@router.put("/me/password", status_code=204)
def change_my_password(body: PasswordChangeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다")
    if not PASSWORD_PATTERN.match(body.new_password):
        raise HTTPException(status_code=400, detail="비밀번호는 영문 대문자, 소문자, 숫자, 특수문자를 모두 포함한 8~20자여야 합니다")
    if verify_password(body.new_password, user.password):
        raise HTTPException(status_code=400, detail="현재 비밀번호와 다른 비밀번호를 입력해주세요")
    user.password = hash_password(body.new_password)
    db.commit()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# 후기 SNS·홈페이지 홍보 활용 동의·철회 (선택 동의라 언제든 바꿀 수 있다)
@router.put("/me/review-marketing", response_model=UserResponse)
def set_review_marketing_consent(body: ReviewMarketingConsentRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = _utcnow()
    if body.agreed and user.review_marketing_agreed_at is None:
        user.review_marketing_agreed_at = now
    elif not body.agreed and user.review_marketing_agreed_at is not None:
        user.review_marketing_agreed_at = None
        user.review_marketing_withdrawn_at = now
    db.commit()
    db.refresh(user)
    return user


# 회원 탈퇴 — 비밀번호로 본인 확인 후 개인정보 삭제 (법정 보존 정보는 분리 보관, app/crud/withdrawal.py)
@router.delete("/me", status_code=204)
def withdraw_me(body: WithdrawRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.password, user.password):
        raise HTTPException(status_code=400, detail="비밀번호가 올바르지 않습니다")
    user_id = user.user_id
    db.rollback()   # 위 조회의 트랜잭션을 끝내고, 탈퇴 처리에서 회원 행을 잠그고 다시 읽는다
    try:
        review_images = withdrawal_crud.withdraw(db, user_id)
    except withdrawal_crud.WithdrawalError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    for url in review_images:
        delete_image(url)

MIN_SIGNUP_AGE = 14


# 오늘(한국 날짜) 기준 만 나이
def _korean_age(birth: date) -> int:
    today = (datetime.now(timezone.utc) + timedelta(hours=9)).date()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


# 포트원 본인인증 결과를 조회해서, 인증이 안 됐거나 이미 가입된 번호거나 만 14세 미만이면 400
def _verify_identity(identity_verification_id: str, db: Session) -> dict:
    try:
        identity = get_verified_identity(identity_verification_id)
    except PortOneError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 만 14세 미만은 법정대리인 동의 절차가 없어 가입을 받지 않는다 (이용약관 제4조)
    # 생년월일은 이 확인에만 쓰고 저장하지 않는다
    birth = identity.get("birth_date")
    if birth is None:
        raise HTTPException(status_code=400, detail="본인인증 결과에서 생년월일을 확인하지 못했습니다. 다시 인증해주세요")
    if _korean_age(birth) < MIN_SIGNUP_AGE:
        raise HTTPException(status_code=400, detail="만 14세 미만은 가입할 수 없습니다")
    if db.query(User).filter(User.phone == identity["phone"]).first():
        raise HTTPException(status_code=400, detail="이미 가입된 휴대폰 번호입니다")
    return identity

# 휴대폰 번호를 숫자만 남겨 저장 형식(01012345678)으로 맞춘다. 형식이 틀리면 None
def _normalize_phone(value: str) -> Optional[str]:
    phone = re.sub(r"\D", "", value)
    return phone if re.fullmatch(r"01\d{8,9}", phone) else None

# 본인인증 결과 확인 (가입 폼에 인증된 번호를 보여주기 위함)
@router.post("/identity-verification", response_model=IdentityVerifyResponse)
def verify_identity(body: IdentityVerifyRequest, db: Session = Depends(get_db)):
    identity = _verify_identity(body.identity_verification_id, db)
    return IdentityVerifyResponse(name=identity["name"], phone=identity["phone"])

# 회원가입
@router.post("/signup", response_model=UserResponse)
def signup(body: UserSignup, db: Session = Depends(get_db)):
    # 필수 동의
    if not body.terms_agreed:
        raise HTTPException(status_code=400, detail="이용약관에 동의해야 가입할 수 있습니다")
    if not body.age_14_confirmed:
        raise HTTPException(status_code=400, detail="만 14세 이상만 가입할 수 있습니다")
    # 탈퇴 회원 가명 값(app/crud/withdrawal.py)과 겹치지 않게 이 글자는 못 쓴다
    if withdrawal_crud.WITHDRAWN_MARK in body.login_id or withdrawal_crud.WITHDRAWN_MARK in body.nickname:
        raise HTTPException(status_code=400, detail=f"아이디와 닉네임에는 '{withdrawal_crud.WITHDRAWN_MARK}' 문자를 쓸 수 없습니다")
    # 중복 확인
    if db.query(User).filter(User.login_id == body.login_id).first():
        raise HTTPException(status_code=400, detail="이미 사용중인 아이디입니다")
    if db.query(User).filter(User.nickname == body.nickname).first():
        raise HTTPException(status_code=400, detail="이미 사용중인 닉네임입니다")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="이미 사용중인 이메일입니다")
    # 전화번호·이름은 클라이언트 값을 믿지 않고 포트원에서 인증된 값을 쓴다 (이미 가입된 번호면 400)
    identity = _verify_identity(body.identity_verification_id, db)
    referrer = None
    if body.referral_code and body.referral_code.strip():
        try:
            referrer = referral_crud.resolve_referrer(db, body.referral_code)
        except referral_crud.ReferralError as e:
            raise HTTPException(status_code=400, detail=str(e))

    now = _utcnow()
    user = User(
        login_id=body.login_id,
        nickname=body.nickname,
        email=body.email,
        password=hash_password(body.password),
        name=identity["name"],
        phone=identity["phone"],
        phone_verified_at=identity["verified_at"],
        referral_code=referral_crud.new_referral_code(db),
        referred_by_user_id=referrer.user_id if referrer else None,
        terms_agreed_at=now,
        age_14_confirmed_at=now,
        review_marketing_agreed_at=now if body.review_marketing_agreed else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# 로그인
@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, db: Session = Depends(get_db)):
    # DB에서 유저 찾기
    user = db.query(User).filter(User.login_id == body.login_id, User.deleted_at.is_(None)).first()

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
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다")

    user = db.query(User).filter(User.user_id == user_id, User.deleted_at.is_(None)).first()
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
    elif body.field == "phone":
        phone = _normalize_phone(body.value)
        if not phone:
            return DuplCheckResponse(available=False, message="올바른 휴대폰 번호를 입력해주세요")
        exists = db.query(User).filter(User.phone == phone).first()
        label = "휴대폰 번호"

    if exists:
        return DuplCheckResponse(available=False, message=f"이미 사용중인 {label}입니다")
    return DuplCheckResponse(available=True, message=f"사용 가능한 {label}입니다")