import logging

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db, SessionLocal
from app.core.security import decode_token
from app.models.user import User
from app.models.privacy import AdminAccessLog

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")
    # 리프레시 토큰(type=refresh)은 새 액세스 토큰을 받을 때만 쓸 수 있다
    if payload.get("type") != "user":
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    user = db.query(User).filter(User.user_id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")
    _mark_admin_mfa(user, payload)
    return user


# 이 요청의 토큰이 관리자 2단계 인증(OTP)을 거쳐 발급됐는지 user에 표시해 둔다 (DB 컬럼이 아닌 요청 동안만 쓰는 값).
# OTP를 DB에서 해제(totp_enabled_at 비움)하면 이미 받은 토큰도 관리자 권한을 잃는다
def _mark_admin_mfa(user: User, payload: dict) -> None:
    user.admin_mfa = payload.get("mfa") is True and user.totp_enabled_at is not None


# 관리자 권한을 쓸 수 있는지 — is_admin이면서 2단계 인증을 거친 토큰이어야 한다.
# 남의 비공개 문의 보기·후기 삭제처럼 일반 API 안에서 관리자 권한을 쓸 때 is_admin 대신 이걸 본다
def has_admin_access(user: Optional[User]) -> bool:
    return bool(user is not None and user.is_admin and getattr(user, "admin_mfa", False))


ACTIONS = {"GET": "조회", "HEAD": "조회", "POST": "등록", "PUT": "수정", "PATCH": "수정", "DELETE": "삭제"}


# 접속 IP — 앞단 프록시(Azure)는 X-Forwarded-For 맨 뒤에 실제 접속 IP를 덧붙인다 (Azure는 "IP:포트" 형태로 줄 때가 있다).
# 맨 앞 값은 접속자가 헤더를 직접 보내 아무 값이나 넣을 수 있으므로 쓰지 않고, 뒤에서 TRUSTED_PROXY_COUNT 번째 값을 쓴다
# (Cloudflare → Azure 순으로 거치면 맨 뒤는 Cloudflare 서버 IP이므로 2로 둔다)
def client_ip(request: Request) -> Optional[str]:
    forwarded = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",") if p.strip()]
    if forwarded:
        hops = max(1, settings.TRUSTED_PROXY_COUNT)
        ip = forwarded[-hops] if len(forwarded) >= hops else forwarded[0]
        if ip.count(":") == 1:   # IPv4:포트
            ip = ip.split(":")[0]
        return ip.strip("[]")[:45] or None
    return request.client.host if request.client else None


# 관리자 접속기록 — 처리방침 제9조 "접속기록 최소 2년 보관". 누가·언제·어디서·무엇을(경로·쿼리) 했는지 남긴다.
# 요청 DB 세션과 따로 저장해서, 요청이 실패해 롤백돼도 기록은 남는다
def _log_admin_access(admin_id: int, request: Request) -> None:
    path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    db = SessionLocal()
    try:
        db.add(AdminAccessLog(
            admin_id=admin_id,
            ip=client_ip(request),
            method=request.method[:10],
            action=ACTIONS.get(request.method, request.method)[:10],
            path=path[:500],
            user_agent=(request.headers.get("user-agent") or "")[:300] or None,
        ))
        db.commit()
    finally:
        db.close()


# 관리자 접속기록을 남긴다. 못 남기면 503으로 요청을 막는다 (기록 없이 개인정보를 조회하지 못하게)
# 관리자 전용 API는 get_current_admin이 알아서 부르고, 일반 API에서 관리자 권한으로 개인정보를 다룰 때는 직접 부른다
def log_admin_access(admin: User, request: Request) -> None:
    try:
        _log_admin_access(admin.user_id, request)
    except Exception:
        logging.exception("admin access log failed")
        raise HTTPException(status_code=503, detail="접속기록을 남기지 못해 요청을 처리하지 않았습니다. 잠시 후 다시 시도해 주세요")


# 관리자 API — 2단계 인증(OTP)을 거친 토큰만 받는다. 프론트는 detail.code로 다음 화면을 정한다
#   mfa_setup_required: 아직 OTP를 등록하지 않음 → 등록 화면 / mfa_required: OTP 없이 받은 예전 토큰 → 다시 로그인
def get_current_admin(request: Request, user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    if not has_admin_access(user):
        if user.totp_enabled_at is None:
            detail = {"code": "mfa_setup_required", "message": "관리자 2단계 인증(OTP)을 먼저 등록해주세요"}
        else:
            detail = {"code": "mfa_required", "message": "2단계 인증으로 다시 로그인해주세요"}
        raise HTTPException(status_code=403, detail=detail)
    log_admin_access(user, request)
    return user


# 로그인 안 해도 되는 API에서, 로그인했으면 누구인지 알아낸다 (토큰이 없거나 잘못되면 None)
def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        return None
    if payload.get("type") != "user":
        return None
    user = db.query(User).filter(User.user_id == user_id, User.deleted_at.is_(None)).first()
    if user is not None:
        _mark_admin_mfa(user, payload)
    return user
