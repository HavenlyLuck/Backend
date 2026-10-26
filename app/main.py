import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import SessionLocal
from app.crud import raffle as raffle_crud
from app.crud import payment as payment_crud
from app.routers import user, admin, raffle, point, store, storage, address, avatar_item, notice, kuji, payment, inventory, finance

SETTLE_INTERVAL_SECONDS = 5
# 결제 정리(결제 후 창을 닫은 주문 지급, 카드 취소 재시도)는 포트원 API를 부르므로 더 드물게
PAYMENT_SETTLE_EVERY = 6   # SETTLE_INTERVAL_SECONDS × 6 = 30초마다


def settle_raffles_once():
    db = SessionLocal()
    try:
        raffle_crud.settle_raffles(db)
    finally:
        db.close()


def settle_payments_once():
    db = SessionLocal()
    try:
        payment_crud.settle_payments(db)
    finally:
        db.close()


# 응모 기간 만료 취소·환불과 매진 1분 뒤 자동 추첨, 결제 정리는 여기서만 처리한다.
# API 요청마다 하면 원격 DB 왕복이 쌓여 모든 화면이 느려지므로 요청 경로에서는 하지 않는다.
# (서버 프로세스가 여러 개여도 settle_raffles가 행 잠금으로 한 번만 처리한다)
async def settle_loop():
    tick = 0
    while True:
        try:
            await asyncio.to_thread(settle_raffles_once)
        except Exception:
            logging.exception("raffle settle failed")
        if tick % PAYMENT_SETTLE_EVERY == 0:
            try:
                await asyncio.to_thread(settle_payments_once)
            except Exception:
                logging.exception("payment settle failed")
        tick += 1
        await asyncio.sleep(SETTLE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(settle_loop())
    yield
    task.cancel()


app = FastAPI(title="HavenlyLuck API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://havenlyluck-frontend.vercel.app",
        "https://havenlyluck.com",
        "https://www.havenlyluck.com",
    ],
    # 로컬 개발 — 같은 와이파이의 다른 기기에서 http://<사설 IP>:3000 으로 접속하는 경우
    allow_origin_regex=r"http://(192\.168|10|172\.(1[6-9]|2\d|3[01]))(\.\d{1,3}){2,3}:3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(user.router, prefix="/users", tags=["users"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(raffle.router, prefix="/raffles", tags=["raffles"])
app.include_router(point.router, prefix="/points", tags=["points"])
app.include_router(store.router, prefix="/store-products", tags=["store"])
app.include_router(storage.router, prefix="/storage", tags=["storage"])
app.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
app.include_router(finance.router, prefix="/finance", tags=["finance"])
app.include_router(address.router, prefix="/addresses", tags=["addresses"])
app.include_router(avatar_item.router, prefix="/avatar-items", tags=["avatar-items"])
app.include_router(notice.router, prefix="/notices", tags=["notices"])
app.include_router(kuji.router, prefix="/kuji", tags=["kuji"])
app.include_router(payment.router, prefix="/payments", tags=["payments"])

@app.get("/server_ok")
def health_check():
    return {"status": "ok"}