# app/routers/point.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, Literal

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.point import PointWallet
from app.schemas.point import PointWalletResponse, PointTransactionResponse
from app.crud import point as point_crud

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


# 내 포인트 거래 내역 조회
@router.get("/transactions", response_model=list[PointTransactionResponse])
def get_my_point_transactions(
    point_type: Optional[Literal["woon", "ssal"]] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return point_crud.get_point_transactions(db, user.user_id, point_type=point_type)
