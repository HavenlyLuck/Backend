import logging

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from typing import Optional
from sqlalchemy.orm import Session

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
    return user


ACTIONS = {"GET": "조회", "HEAD": "조회", "POST": "등록", "PUT": "수정", "PATCH": "수정", "DELETE": "삭제"}


# 접속 IP — Azure 앞단 프록시를 거치면 X-Forwarded-For 첫 값이 실제 접속 IP다 (Azure는 "IP:포트" 형태로 줄 때가 있다)
def client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
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


def get_current_admin(request: Request, user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
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
    return db.query(User).filter(User.user_id == user_id, User.deleted_at.is_(None)).first()
