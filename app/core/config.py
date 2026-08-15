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
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str


    class Config:
        env_file = ".env"

settings = Settings()

# 응모권 1장당 가격 (운포인트, 고정값)
RAFFLE_TICKET_PRICE = 1000
# 응모 상품 진행 기간 (등록 시점 기준)
RAFFLE_DURATION_HOURS = 24