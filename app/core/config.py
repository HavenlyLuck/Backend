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
    # 앞단 프록시 수 — 접속 IP는 X-Forwarded-For의 뒤에서 이 번째 값을 쓴다 (app/core/dependencies.py client_ip)
    # Azure App Service만 거치면 1, Cloudflare → Azure 순으로 거치면 2
    TRUSTED_PROXY_COUNT: int = 1
    # 관리자 OTP 비밀키 암호화 키. 비우면 SECRET_KEY에서 만든다 (그 경우 SECRET_KEY를 바꾸면 OTP를 다시 등록해야 한다)
    TOTP_ENCRYPTION_KEY: Optional[str] = None
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    # 도로명주소 검색 API 승인키 (business.juso.go.kr 에서 발급). 없으면 주소 검색이 비활성화된다
    JUSO_API_KEY: Optional[str] = None
    # 포트원 V2 API Secret (관리자콘솔 > 연동 정보 > 식별코드·API Keys). 없으면 본인인증이 비활성화된다
    PORTONE_API_SECRET: Optional[str] = None
    # 포트원 상점 아이디 (store-xxxx). 선택값
    PORTONE_STORE_ID: Optional[str] = None
    # 스마트택배(스윗트래커) 배송 조회 API 키 (tracking.sweettracker.co.kr 에서 발급). 없으면 배송 조회가 비활성화된다
    SWEETTRACKER_API_KEY: Optional[str] = None
    # 솔라피 카카오 알림톡 (console.solapi.com) — API 키·시크릿, 카카오 채널 pfId, 템플릿 ID 4개.
    # 키·pfId가 없으면 알림톡을 보내지 않는다. 템플릿 ID가 비어 있는 알림도 보내지 않는다 (app/services/alimtalk.py)
    SOLAPI_API_KEY: Optional[str] = None
    SOLAPI_API_SECRET: Optional[str] = None
    SOLAPI_PF_ID: Optional[str] = None
    SOLAPI_TEMPLATE_RAFFLE_ENTERED: Optional[str] = None    # 응모 완료 — 응모 접수
    SOLAPI_TEMPLATE_RAFFLE_SOLD_OUT: Optional[str] = None   # 응모 완성 — 매진, 추첨 예정
    SOLAPI_TEMPLATE_RAFFLE_FAILED: Optional[str] = None     # 응모 실패(자동 취소) — 기간 만료로 취소·환불
    SOLAPI_TEMPLATE_SHIPPED: Optional[str] = None           # 배송 출발
    # 오픈 이벤트 — 이 날짜(한국 시간, 그날 포함)까지 가입하면 쌀 응모권 1장을 준다. 비우면(빈 문자열) 이벤트 없음
    SIGNUP_EVENT_END_DATE: Optional[str] = "2026-12-22"


    class Config:
        env_file = ".env"

settings = Settings()

# 배송 신청 1건당 배송비(원) — 한 번에 신청한 상품은 한 박스로 보내므로 몇 개든 1번만 낸다
SHIPPING_FEE = 4000
# 결제 상점 구매 때 쌀포인트로 할인받을 수 있는 최대 비율 (구매 금액의 20%, 1P = 1원)
STORE_POINT_DISCOUNT_RATE_PERCENT = 20

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
# 상점 → 응모 전환 모금: 응모권(가격 ÷ 응모권 가격)의 1/3이 팔리면 응모 상품으로 전환된다.
# 첫 응모권이 팔린 뒤 이 기간 안에 못 모으면 전부 환불하고, 묶어 둔 재고 1개는 상점으로 돌아간다
FUNDING_THRESHOLD_DIVISOR = 3
FUNDING_DURATION_DAYS = 3
# 전환된 응모 상품의 응모 기간 (전환 시점부터)
FUNDING_RAFFLE_DURATION_DAYS = 1
# 응모권 1/3이 최소 1장 이상 되도록 — 이 가격(원) 이상인 상품만 전환 모금을 열 수 있다
FUNDING_MIN_PRICE = 3000
# 응모 상품으로 전환된 뒤 모금 때 산 응모권을 취소하면, 이 기간 동안 전환 응모권을 살 수 없다
FUNDING_CANCEL_BAN_DAYS = 3
# 응모권이 매진된 뒤 자동 추첨까지 기다리는 시간 (이 동안 응모자들이 추첨 화면을 준비한다)
RAFFLE_DRAW_DELAY_SECONDS = 1 * 60
