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


    class Config:
        env_file = ".env"

settings = Settings()

# 응모권 1장당 가격 (운포인트, 고정값)
RAFFLE_TICKET_PRICE = 1000
# 응모 상품 진행 기간 (등록 시점 기준, 관리자가 등록할 때 이 중에서 선택)
RAFFLE_DURATION_DAYS_OPTIONS = (1, 2, 3)# 응모권이 매진된 뒤 자동 추첨까지 기다리는 시간 (이 동안 응모자들이 추첨 화면을 준비한다)
RAFFLE_DRAW_DELAY_SECONDS = 5 * 60
