from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14  # 14일
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    # 도로명주소 검색 API 승인키 (business.juso.go.kr 에서 발급). 없으면 주소 검색이 비활성화된다
    JUSO_API_KEY: Optional[str] = None


    class Config:
        env_file = ".env"

settings = Settings()

# 응모권 1장당 가격 (운포인트, 고정값)
RAFFLE_TICKET_PRICE = 1000
# 응모 상품 진행 기간 (등록 시점 기준, 관리자가 등록할 때 이 중에서 선택)
RAFFLE_DURATION_DAYS_OPTIONS = (1, 2, 3)
# 테스트용 — 값이 있으면 관리자가 고른 기간 대신 등록 시점부터 이 분(minute) 뒤에 마감한다. 운영에서는 None
RAFFLE_DURATION_OVERRIDE_MINUTES = None
# 쿠지 제비 1장 기본 가격(운포인트)과 한 판에 만들 수 있는 최대 제비 수
KUJI_TICKET_PRICE = 10000
KUJI_MAX_TICKETS = 1000
# 한 번에 뽑을 수 있는 최대 제비 수
KUJI_MAX_DRAW = 10
# 응모권이 매진된 뒤 자동 추첨까지 기다리는 시간 (이 동안 응모자들이 추첨 화면을 준비한다)
RAFFLE_DRAW_DELAY_SECONDS = 1 * 60
