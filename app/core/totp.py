"""관리자 2단계 인증 — OTP 앱(Google Authenticator 등)이 30초마다 바꾸는 6자리 코드 (RFC 6238 TOTP).

비밀키는 DB에 암호화해서 둔다. DB가 통째로 새도 키 없이는 OTP를 만들 수 없게.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from typing import Optional
from urllib.parse import quote

from cryptography.fernet import Fernet

from app.core.config import settings

ISSUER = "천운"
STEP_SECONDS = 30
DIGITS = 6
# 휴대폰 시계가 조금 어긋나도 받아 준다 — 앞뒤 30초씩
ALLOWED_DRIFT_STEPS = 1


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()   # 160비트, 32글자


def _code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** DIGITS)
    return f"{value:0{DIGITS}d}"


def verify(secret: str, code: str, last_step: Optional[int]) -> Optional[int]:
    """코드가 맞으면 그 코드의 구간 번호를, 틀리면 None. last_step 이하(이미 쓴 코드)는 받지 않는다."""
    code = (code or "").replace(" ", "").strip()
    if len(code) != DIGITS or not code.isdigit():
        return None
    now_step = int(time.time()) // STEP_SECONDS
    for step in range(now_step - ALLOWED_DRIFT_STEPS, now_step + ALLOWED_DRIFT_STEPS + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(_code_at(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, account: str) -> str:
    label = quote(f"{ISSUER}:{account}")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}"
        f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"
    )


def _fernet() -> Fernet:
    source = settings.TOTP_ENCRYPTION_KEY or f"totp:{settings.SECRET_KEY}"
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(source.encode()).digest()))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
