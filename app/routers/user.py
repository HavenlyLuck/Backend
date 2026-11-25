import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database import get_db
from app.models.user import User, UsedIdentityVerification
from app.models.free_ticket import FreeTicket
from sqlalchemy.exc import IntegrityError
from app.schemas.user import (
    UserSignup, UserLogin, UserResponse, TokenResponse,
    RefreshRequest, RefreshResponse, DuplCheckRequest, DuplCheckResponse,
    IdentityVerifyRequest, IdentityVerifyResponse, GuardianVerifyRequest, GuardianVerifyResponse, PasswordChangeRequest,
    WithdrawRequest, ReviewMarketingConsentRequest,
    FindIdRequest, FindIdResponse, PasswordResetCheckRequest, PasswordResetRequest,
    SignupResponse, TotpSetupResponse, TotpEnableRequest,
)
from app.core.security import hash_password, verify_password, verify_password_or_dummy, create_token, decode_token
from app.core.dependencies import get_current_user, client_ip, log_admin_access
from app.core import throttle
from app.core import totp
from app.crud import referral as referral_crud
from app.crud import withdrawal as withdrawal_crud
from app.schemas.avatar import AvatarConfig
from app.core.avatar_items import AVATAR_ITEMS, AVATAR_ITEM_SLOTS
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
    owned = avatar_item_crud.get_owned_item_ids(db, user.user_id)
    for slot in AVATAR_ITEM_SLOTS:
        item_id = getattr(body, slot)
        if item_id is None:
            continue
        item = AVATAR_ITEMS.get(item_id)
        if item is None or item["slot"] != slot:
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
# 만 19세 미만(민법상 미성년자)은 보호자(법정대리인) 본인인증과 동의가 있어야 가입된다
ADULT_AGE = 19


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
    # 번호를 바꿔도 같은 사람은 한 계정만 (CI는 사람마다 하나)
    if identity.get("ci") and db.query(User).filter(User.ci == identity["ci"]).first():
        raise HTTPException(status_code=400, detail="이미 가입된 회원입니다. 아이디 찾기를 이용해주세요")
    identity["guardian_required"] = _korean_age(birth) < ADULT_AGE
    return identity


# 보호자(법정대리인) 본인인증 확인 — 만 19세 이상이고 가입자 본인과 다른 사람이어야 한다.
# 같은 보호자 인증을 다른 가입에 다시 쓰지 못하게 가입 때 사용 기록을 남긴다
def _verify_guardian(guardian_verification_id: str, minor: dict, minor_verification_id: str, db: Session) -> dict:
    if guardian_verification_id == minor_verification_id:
        raise HTTPException(status_code=400, detail="보호자 본인인증은 가입자와 다른 분이 해야 합니다")
    if db.get(UsedIdentityVerification, guardian_verification_id):
        raise HTTPException(status_code=400, detail="이미 사용한 보호자 본인인증입니다. 다시 인증해주세요")
    try:
        guardian = get_verified_identity(guardian_verification_id)
    except PortOneError as e:
        raise HTTPException(status_code=400, detail=f"보호자 {e}")
    birth = guardian.get("birth_date")
    if birth is None:
        raise HTTPException(status_code=400, detail="보호자 본인인증 결과에서 생년월일을 확인하지 못했습니다. 다시 인증해주세요")
    if _korean_age(birth) < ADULT_AGE:
        raise HTTPException(status_code=400, detail="보호자는 만 19세 이상이어야 합니다")
    same_ci = guardian.get("ci") and guardian.get("ci") == minor.get("ci")
    if same_ci or guardian["phone"] == minor["phone"]:
        raise HTTPException(status_code=400, detail="보호자 본인인증은 가입자와 다른 분이 해야 합니다")
    return guardian

# 휴대폰 번호를 숫자만 남겨 저장 형식(01012345678)으로 맞춘다. 형식이 틀리면 None
def _normalize_phone(value: str) -> Optional[str]:
    phone = re.sub(r"\D", "", value)
    return phone if re.fullmatch(r"01\d{8,9}", phone) else None

# 본인인증 결과 확인 (가입 폼에 인증된 번호를 보여주기 위함)
@router.post("/identity-verification", response_model=IdentityVerifyResponse)
def verify_identity(body: IdentityVerifyRequest, db: Session = Depends(get_db)):
    identity = _verify_identity(body.identity_verification_id, db)
    return IdentityVerifyResponse(
        name=identity["name"], phone=identity["phone"], guardian_required=identity["guardian_required"],
    )


# 보호자 본인인증 결과 확인 (가입 폼에 보호자 이름을 보여주기 위함). 가입자 본인인증이 유효해야 한다
@router.post("/guardian-verification", response_model=GuardianVerifyResponse)
def verify_guardian(body: GuardianVerifyRequest, db: Session = Depends(get_db)):
    minor = _verify_identity(body.minor_identity_verification_id, db)
    if not minor["guardian_required"]:
        raise HTTPException(status_code=400, detail="만 19세 이상은 보호자 본인인증이 필요 없습니다")
    guardian = _verify_guardian(body.identity_verification_id, minor, body.minor_identity_verification_id, db)
    return GuardianVerifyResponse(name=guardian["name"])

# 회원가입
KST = timezone(timedelta(hours=9))


# 오픈 이벤트 기간인지 — SIGNUP_EVENT_END_DATE(한국 날짜, 그날 23:59까지)
def _signup_event_active() -> bool:
    end = (settings.SIGNUP_EVENT_END_DATE or "").strip()
    if not end:
        return False
    try:
        return datetime.now(KST).date() <= date.fromisoformat(end)
    except ValueError:
        return False


@router.post("/signup", response_model=SignupResponse)
def signup(body: UserSignup, db: Session = Depends(get_db)):
    # 필수 동의
    if not body.terms_agreed:
        raise HTTPException(status_code=400, detail="이용약관에 동의해야 가입할 수 있습니다")
    if not body.age_14_confirmed:
        raise HTTPException(status_code=400, detail="만 14세 이상만 가입할 수 있습니다")
    # 탈퇴 회원 가명 값(app/crud/withdrawal.py)과 겹치지 않게 이 글자는 못 쓴다
    if withdrawal_crud.WITHDRAWN_MARK in body.login_id or withdrawal_crud.WITHDRAWN_MARK in body.nickname:
        raise HTTPException(status_code=400, detail=f"아이디와 닉네임에는 '{withdrawal_crud.WITHDRAWN_MARK}' 문자를 쓸 수 없습니다")
    # 아이디는 영문·숫자만, 비밀번호는 공백 없는 영문 키보드 문자만 (한글 등 불가)
    if not re.fullmatch(r"[A-Za-z0-9]{5,20}", body.login_id):
        raise HTTPException(status_code=400, detail="아이디는 영문·숫자 5~20자로 입력해주세요")
    if not re.fullmatch(r"[\x21-\x7E]+", body.password):
        raise HTTPException(status_code=400, detail="비밀번호는 영문, 숫자, 특수문자만 사용할 수 있습니다")
    # 중복 확인
    if db.query(User).filter(User.login_id == body.login_id).first():
        raise HTTPException(status_code=400, detail="이미 사용중인 아이디입니다")
    if db.query(User).filter(User.nickname == body.nickname).first():
        raise HTTPException(status_code=400, detail="이미 사용중인 닉네임입니다")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="이미 사용중인 이메일입니다")
    # 전화번호·이름은 클라이언트 값을 믿지 않고 포트원에서 인증된 값을 쓴다 (이미 가입된 번호면 400)
    identity = _verify_identity(body.identity_verification_id, db)
    # 만 19세 미만 — 보호자 본인인증 + 보호자 동의가 있어야 가입된다
    guardian = None
    if identity["guardian_required"]:
        if not body.guardian_identity_verification_id:
            raise HTTPException(status_code=400, detail="만 19세 미만은 보호자(법정대리인) 본인인증이 필요합니다")
        if not body.guardian_consent:
            raise HTTPException(status_code=400, detail="보호자(법정대리인)의 가입 동의가 필요합니다")
        guardian = _verify_guardian(body.guardian_identity_verification_id, identity, body.identity_verification_id, db)
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
        ci=identity.get("ci"),
        referral_code=referral_crud.new_referral_code(db),
        referred_by_user_id=referrer.user_id if referrer else None,
        terms_agreed_at=now,
        age_14_confirmed_at=now,
        review_marketing_agreed_at=now if body.review_marketing_agreed else None,
        guardian_name=guardian["name"] if guardian else None,
        guardian_phone=guardian["phone"] if guardian else None,
        guardian_ci=guardian.get("ci") if guardian else None,
        guardian_consented_at=now if guardian else None,
    )
    db.add(user)
    if guardian:
        db.add(UsedIdentityVerification(
            identity_verification_id=body.guardian_identity_verification_id, purpose="guardian_consent",
        ))
    event_ticket = _signup_event_active()
    try:
        if event_ticket:
            # 오픈 이벤트 가입 선물 — 쌀 응모권 1장을 보관함에 (가입과 같은 트랜잭션)
            db.flush()
            db.add(FreeTicket(user_id=user.user_id, kind="signup_event"))
        db.commit()
    except IntegrityError:
        # 같은 보호자 인증으로 동시에 가입한 경우, 또는 같은 아이디·번호로 동시에 가입한 경우
        db.rollback()
        raise HTTPException(status_code=400, detail="가입을 처리하지 못했습니다. 다시 시도해주세요")
    db.refresh(user)
    return SignupResponse.model_validate(user).model_copy(update={"signup_event_ticket": event_ticket})


# ── 로그인 · 무차별 대입 방어 ─────────────────────────────────────────
# IP마다 1분에 10번까지 (성공·실패 모두 센다). 아이디별 실패 잠금은 app/core/throttle.py
LOGIN_IP_LIMIT = 10
LOGIN_IP_WINDOW_SECONDS = 60
# 관리자가 OTP로 받은 리프레시 토큰은 하루만 쓴다 (관리자 세션이 2주씩 이어지지 않게)
ADMIN_REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24


# 토큰 발급 — mfa: 관리자가 2단계 인증(OTP)까지 거쳤는지. 이게 있어야 관리자 API를 쓸 수 있다 (get_current_admin)
def _issue_tokens(user: User, mfa: bool) -> dict:
    extra = {"mfa": True} if mfa else {}
    access_token = create_token({"sub": str(user.user_id), "type": "user", "is_admin": user.is_admin, **extra})
    refresh_token = create_token(
        {"sub": str(user.user_id), "type": "refresh", **extra},
        expires_delta=ADMIN_REFRESH_TOKEN_EXPIRE_MINUTES if mfa else settings.REFRESH_TOKEN_EXPIRE_MINUTES,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "is_admin": user.is_admin,
    }


# 로그인
@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, request: Request, db: Session = Depends(get_db)):
    throttle.rate_limit("login-ip", client_ip(request), LOGIN_IP_LIMIT, LOGIN_IP_WINDOW_SECONDS, "로그인 시도가 너무 많아요.")
    throttle.check_login_lock(body.login_id)

    user = db.query(User).filter(User.login_id == body.login_id, User.deleted_at.is_(None)).first()

    # 유저 없거나 비밀번호 틀리면 에러 — 없는 아이디도 bcrypt 비교를 해서 응답 시간을 맞추고, 실패 횟수도 똑같이 센다
    if not verify_password_or_dummy(body.password, user.password if user else None):
        throttle.record_login_failure(body.login_id)
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")

    # 관리자 2단계 인증 — OTP를 등록한 관리자는 앱의 6자리 코드까지 맞아야 한다
    mfa = False
    if user.is_admin and user.totp_enabled_at is not None:
        if not body.otp_code:
            raise HTTPException(status_code=401, detail={
                "code": "otp_required",
                "message": "OTP 앱에 표시된 6자리 인증 코드를 입력해주세요",
            })
        # 같은 코드를 동시에 두 번 쓰지 못하게 행을 잠그고 확인한다
        me = db.query(User).filter(User.user_id == user.user_id).with_for_update().one()
        step = totp.verify(totp.decrypt_secret(me.totp_secret), body.otp_code, me.totp_last_step)
        if step is None:
            db.rollback()
            throttle.record_login_failure(body.login_id)
            raise HTTPException(status_code=401, detail={
                "code": "otp_invalid",
                "message": "인증 코드가 올바르지 않습니다. 앱에 표시된 새 코드를 입력해주세요",
            })
        me.totp_last_step = step
        db.commit()
        mfa = True

    throttle.clear_login_failures(body.login_id)
    return _issue_tokens(user, mfa)

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

    # 2단계 인증 표시는 리프레시 토큰에 있던 것만 이어받는다 (OTP를 DB에서 해제했으면 떼어 낸다)
    mfa = payload.get("mfa") is True and user.is_admin and user.totp_enabled_at is not None
    access_token = create_token({
        "sub": str(user.user_id),
        "type": "user",
        "is_admin": user.is_admin,
        **({"mfa": True} if mfa else {}),
    })

    return {"access_token": access_token, "token_type": "bearer", "is_admin": user.is_admin}


# ── 관리자 2단계 인증(OTP) 등록 ─────────────────────────────────────────
# 관리자 API는 OTP를 거친 토큰만 받으므로(get_current_admin), 관리자는 처음 한 번 여기서 등록한다.
# 등록을 마친 뒤에는 API로 다시 등록·해제할 수 없다 (비밀번호를 훔친 사람이 자기 휴대폰으로 바꿔 등록하지 못하게).
# 휴대폰을 잃어버리면 DB에서 해당 관리자의 totp_secret·totp_enabled_at·totp_last_step을 비우고 다시 등록한다

def _require_admin_without_totp(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    if user.totp_enabled_at is not None:
        raise HTTPException(status_code=400, detail="이미 2단계 인증을 등록했습니다")


# 등록 1단계 — 새 비밀키를 만들어 OTP 앱에 넣을 키·링크를 준다 (다시 부르면 새 키로 바뀐다)
@router.post("/me/2fa/setup", response_model=TotpSetupResponse)
def setup_totp(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin_without_totp(user)
    secret = totp.new_secret()
    user.totp_secret = totp.encrypt_secret(secret)
    user.totp_last_step = None
    db.commit()
    return TotpSetupResponse(secret=secret, otpauth_uri=totp.provisioning_uri(secret, user.login_id))


# 등록 2단계 — 앱에 뜬 코드가 맞으면 등록을 마치고, 2단계 인증을 거친 새 토큰을 준다
@router.post("/me/2fa/enable", response_model=TokenResponse)
def enable_totp(body: TotpEnableRequest, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin_without_totp(user)
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="등록을 처음부터 다시 시작해주세요")
    throttle.rate_limit("totp-enable", str(user.user_id), 10, 300, "인증 코드 확인 시도가 너무 많아요.")

    me = db.query(User).filter(User.user_id == user.user_id).with_for_update().one()
    step = totp.verify(totp.decrypt_secret(me.totp_secret), body.code, None)
    if step is None:
        db.rollback()
        raise HTTPException(status_code=400, detail="인증 코드가 올바르지 않습니다. 앱에 표시된 새 코드를 입력해주세요")
    me.totp_enabled_at = _utcnow()
    me.totp_last_step = step
    db.commit()
    log_admin_access(me, request)   # 관리자 보안 설정 변경도 접속기록에 남긴다
    return _issue_tokens(me, mfa=True)

# ── 아이디·비밀번호 찾기 ─────────────────────────────────────────────
# 본인인증한 사람의 계정을 찾는다. 프론트가 보낸 값은 믿지 않고 포트원에 직접 물어본 결과만 쓴다.
# 1) CI가 같은 계정 (번호를 바꿨어도 찾힌다)
# 2) CI가 없는 예전 가입자: 번호가 같고, 이름이 저장돼 있으면 이름까지 같아야 한다
#    (해지된 번호를 새로 받은 다른 사람이 남의 계정을 찾지 못하게). 찾으면 CI·이름을 채워 둔다
def _find_user_by_identity(identity_verification_id: str, db: Session) -> User:
    try:
        identity = get_verified_identity(identity_verification_id)
    except PortOneError as e:
        raise HTTPException(status_code=400, detail=str(e))

    not_found = HTTPException(status_code=404, detail="본인인증 정보로 가입된 계정이 없습니다")
    ci = identity.get("ci")
    if ci:
        user = db.query(User).filter(User.ci == ci, User.deleted_at.is_(None)).first()
        if user:
            return user
    user = db.query(User).filter(User.phone == identity["phone"], User.deleted_at.is_(None)).first()
    if not user or (user.ci and user.ci != ci):
        raise not_found
    if user.name and identity.get("name") and user.name != identity["name"]:
        raise not_found
    if ci and not user.ci:
        user.ci = ci
    if identity.get("name") and not user.name:
        user.name = identity["name"]
    db.commit()
    return user


# 아이디 찾기 — 본인인증만 하면 가입한 아이디를 알려준다
@router.post("/find-id", response_model=FindIdResponse)
def find_id(body: FindIdRequest, db: Session = Depends(get_db)):
    user = _find_user_by_identity(body.identity_verification_id, db)
    return FindIdResponse(login_id=user.login_id, joined_at=user.created_at)


def _find_user_for_password_reset(login_id: str, identity_verification_id: str, db: Session) -> User:
    user = _find_user_by_identity(identity_verification_id, db)
    if user.login_id != login_id.strip():
        raise HTTPException(status_code=400, detail="입력한 아이디와 본인인증 정보가 일치하지 않습니다")
    if db.get(UsedIdentityVerification, identity_verification_id):
        raise HTTPException(status_code=400, detail="이미 사용한 본인인증입니다. 다시 인증해주세요")
    return user


# 비밀번호 찾기 1단계 — 아이디 주인과 본인인증한 사람이 같은지 확인 (새 비밀번호 입력 화면을 열기 전)
@router.post("/reset-password/check", status_code=204)
def check_password_reset(body: PasswordResetCheckRequest, db: Session = Depends(get_db)):
    _find_user_for_password_reset(body.login_id, body.identity_verification_id, db)


# 비밀번호 찾기 2단계 — 새 비밀번호로 바꾼다. 쓴 본인인증 ID는 기록해서 다시 못 쓰게 한다
@router.post("/reset-password", status_code=204)
def reset_password(body: PasswordResetRequest, db: Session = Depends(get_db)):
    user = _find_user_for_password_reset(body.login_id, body.identity_verification_id, db)
    if not PASSWORD_PATTERN.match(body.new_password):
        raise HTTPException(status_code=400, detail="비밀번호는 영문 대문자, 소문자, 숫자, 특수문자를 모두 포함한 8~20자여야 합니다")
    user.password = hash_password(body.new_password)
    db.add(UsedIdentityVerification(identity_verification_id=body.identity_verification_id, purpose="password_reset"))
    try:
        db.commit()
    except IntegrityError:   # 같은 인증으로 동시에 두 번 요청한 경우
        db.rollback()
        raise HTTPException(status_code=400, detail="이미 사용한 본인인증입니다. 다시 인증해주세요")
    # 본인인증으로 비밀번호를 바꿨으면 로그인 실패 잠금도 바로 풀어 준다
    throttle.clear_login_failures(user.login_id)


# 회원가입 중복확인 — 가입 여부를 알려주는 API라 IP마다 1분에 30번까지만
@router.post("/duplCheck")
def dupl_check(body: DuplCheckRequest, request: Request, db: Session = Depends(get_db)):
    throttle.rate_limit("dupl-ip", client_ip(request), 30, 60, "중복 확인 요청이 너무 많아요.")
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