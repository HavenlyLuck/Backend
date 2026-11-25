"""무차별 대입 방어 — IP별 요청 횟수 제한과 아이디별 로그인 실패 잠금.

서버 프로세스·인스턴스가 여러 개여도 같은 값을 보도록 DB(auth_throttles)에 센다.
요청의 DB 세션과 따로 커밋한다: 요청이 실패해 롤백돼도 센 횟수는 남아야 하기 때문이다.
key에는 IP·아이디 원문 대신 해시를 넣는다 (개인정보를 남기지 않게).
"""
import hashlib
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import SessionLocal
from app.models.auth_throttle import AuthThrottle

# 로그인 실패 잠금 — 같은 아이디로 연속 실패하면 점점 길게 잠근다 (영구 잠금은 하지 않는다:
# 남이 일부러 틀려서 내 계정을 막아 버릴 수 있으므로). 잠긴 사람은 비밀번호 찾기로 바로 풀 수 있다
LOGIN_LOCK_STEPS = (           # (누적 실패 횟수, 잠금 시간) — 큰 것부터
    (15, timedelta(hours=1)),
    (10, timedelta(minutes=15)),
    (5, timedelta(minutes=1)),
)
LOGIN_FAILURE_WINDOW = timedelta(hours=24)   # 실패 횟수는 첫 실패부터 24시간 동안 쌓인다

# 다 지난 카운터는 지운다 (main.py에서 1시간마다)
THROTTLE_RETENTION = timedelta(days=2)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _key(kind: str, value: str) -> str:
    digest = hashlib.sha256(f"{settings.SECRET_KEY}:{kind}:{value}".encode()).hexdigest()
    return f"{kind}:{digest[:48]}"


def _normalize_login_id(login_id: str) -> str:
    # DB 비교가 대소문자를 가리지 않으므로 Admin·admin을 같은 아이디로 센다
    return login_id.strip().lower()


def _minutes_text(seconds: int) -> str:
    return f"{max(1, math.ceil(seconds / 60))}분"


def _row_for_update(db: Session, key: str, now: datetime) -> AuthThrottle:
    row = db.query(AuthThrottle).filter(AuthThrottle.key == key).with_for_update().first()
    if row:
        return row
    row = AuthThrottle(key=key, count=0, window_start=now)
    db.add(row)
    try:
        db.flush()
        return row
    except IntegrityError:   # 다른 요청이 방금 같은 key를 만들었다
        db.rollback()
        return db.query(AuthThrottle).filter(AuthThrottle.key == key).with_for_update().one()


def rate_limit(kind: str, value: Optional[str], limit: int, window_seconds: int, message: str) -> None:
    """value(IP 등)마다 window_seconds 동안 limit번까지만 허용한다. 넘으면 429."""
    if not value:
        return
    key = _key(kind, value)
    window = timedelta(seconds=window_seconds)
    db = SessionLocal()
    try:
        now = _now()
        row = _row_for_update(db, key, now)
        if row.window_start + window <= now:
            row.window_start = now
            row.count = 0
        row.count += 1
        count = row.count
        retry_after = max(1, int((row.window_start + window - now).total_seconds()))
        db.commit()
    finally:
        db.close()
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail=f"{message} {_minutes_text(retry_after)} 뒤에 다시 시도해주세요",
            headers={"Retry-After": str(retry_after)},
        )


def _locked_error(seconds: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail=f"로그인 시도가 너무 많아요. {_minutes_text(seconds)} 뒤에 다시 시도하거나, 비밀번호 찾기로 비밀번호를 다시 설정해주세요",
        headers={"Retry-After": str(seconds)},
    )


def check_login_lock(login_id: str) -> None:
    """이 아이디가 잠겨 있으면 429. 없는 아이디도 똑같이 세고 잠그므로, 잠금 여부로 가입 여부를 알 수 없다."""
    db = SessionLocal()
    try:
        row = db.get(AuthThrottle, _key("login-fail", _normalize_login_id(login_id)))
        locked_until = row.locked_until if row else None
    finally:
        db.close()
    now = _now()
    if locked_until and locked_until > now:
        raise _locked_error(int((locked_until - now).total_seconds()) + 1)


def record_login_failure(login_id: str) -> None:
    """로그인 실패(비밀번호·OTP 틀림)를 센다. 기준 횟수에 닿으면 잠근다."""
    key = _key("login-fail", _normalize_login_id(login_id))
    db = SessionLocal()
    try:
        now = _now()
        row = _row_for_update(db, key, now)
        if row.window_start + LOGIN_FAILURE_WINDOW <= now:
            row.window_start = now
            row.count = 0
            row.locked_until = None
        row.count += 1
        for threshold, duration in LOGIN_LOCK_STEPS:
            if row.count >= threshold:
                row.locked_until = now + duration
                break
        db.commit()
    finally:
        db.close()


def clear_login_failures(login_id: str) -> None:
    """로그인 성공·비밀번호 재설정 뒤 실패 기록을 지운다."""
    db = SessionLocal()
    try:
        db.query(AuthThrottle).filter(
            AuthThrottle.key == _key("login-fail", _normalize_login_id(login_id))
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def purge_expired_throttles(db: Session) -> None:
    cutoff = _now() - THROTTLE_RETENTION
    db.query(AuthThrottle).filter(
        AuthThrottle.window_start < cutoff,
        (AuthThrottle.locked_until.is_(None)) | (AuthThrottle.locked_until < cutoff),
    ).delete(synchronize_session=False)
    db.commit()
