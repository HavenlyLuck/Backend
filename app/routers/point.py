# app/routers/point.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.point import PointWallet
from app.schemas.point import PointWalletResponse

router = APIRouter()


# 내 포인트 조회 (지갑이 없으면 0P로 생성)
@router.get("/me", response_model=PointWalletResponse)
def get_my_points(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wallet = db.query(PointWallet).filter(PointWallet.user_id == user.user_id).first()
    if not wallet:
        wallet = PointWallet(user_id=user.user_id, woon_point=0, ssal_point=0)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet
