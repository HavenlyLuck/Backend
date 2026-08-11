# app/routers/admin.py
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_admin
from app.models.user import User

router = APIRouter()


# 관리자 권한 검증 (프론트에서 /admin 진입 시 호출)
@router.get("/verify")
def verify_admin(admin: User = Depends(get_current_admin)):
    return {"is_admin": True}