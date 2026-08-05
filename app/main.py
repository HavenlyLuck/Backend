from fastapi import FastAPI
from app.routers import user, admin, raffle

app = FastAPI(title="HavenlyLuck API")

# 라우터 등록
app.include_router(user.router, prefix="/users", tags=["users"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(raffle.router, prefix="/raffles", tags=["raffles"])

@app.get("/server_ok")
def health_check():
    return {"status": "ok"}