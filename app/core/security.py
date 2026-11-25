import secrets
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 비밀번호 해시
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# 디비에 저장돼있는 값이랑 비교
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# 없는 아이디로 로그인할 때도 bcrypt 비교를 한 번 해서 응답 시간을 맞춘다
# (없는 아이디만 빨리 실패하면 응답 속도로 가입 여부를 알 수 있다)
_DUMMY_PASSWORD_HASH = pwd_context.hash(secrets.token_urlsafe(16))


def verify_password_or_dummy(plain: str, hashed: Optional[str]) -> bool:
    if hashed is None:
        pwd_context.verify(plain, _DUMMY_PASSWORD_HASH)
        return False
    return pwd_context.verify(plain, hashed)

# JWT 토큰 생성
def create_token(data: dict, expires_delta: int = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_delta or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])