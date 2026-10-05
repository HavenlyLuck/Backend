import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import SessionLocal
from app.crud import raffle as raffle_crud
from app.routers import user, admin, raffle, point, store, storage, address

SETTLE_INTERVAL_SECONDS = 5


def settle_raffles_once():
    db = SessionLocal()
    try:
        raffle_crud.settle_raffles(db)
    finally:
        db.close()


# 응모 기간 만료 취소·환급과 매진 5분 뒤 자동 추첨은 여기서만 처리한다.
# API 요청마다 하면 원격 DB 왕복이 쌓여 모든 화면이 느려지므로 요청 경로에서는 하지 않는다.
# (서버 프로세스가 여러 개여도 settle_raffles가 행 잠금으로 한 번만 처리한다)
async def settle_loop():
    while True:
        try:
            await asyncio.to_thread(settle_raffles_once)
        except Exception:
            logging.exception("raffle settle failed")
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
    allow_origins=["http://localhost:3000", "https://havenlyluck-frontend.vercel.app"],
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
app.include_router(address.router, prefix="/addresses", tags=["addresses"])

@app.get("/server_ok")
def health_check():
    return {"status": "ok"}