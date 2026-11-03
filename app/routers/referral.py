# app/routers/referral.py — 추천인 코드 · 보관함 무료 응모권
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.crud import referral as referral_crud
from app.database import get_db
from app.models.user import User
from app.schemas.referral import FreeTicketResponse, ReferralRegisterRequest, ReferralSummaryResponse

router = APIRouter()


# 내 추천인 코드 · 등록한 추천인 · 등록 가능 여부
@router.get("/me", response_model=ReferralSummaryResponse)
def get_my_referral(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return referral_crud.get_referral_summary(db, user)


# 추천인 등록 — 한 번만, 첫 응모권 구매 전에만
@router.post("/register", response_model=ReferralSummaryResponse)
def register_referrer(body: ReferralRegisterRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        referral_crud.register_referrer(db, user, body.referral_code)
    except referral_crud.ReferralError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    db.refresh(user)
    return referral_crud.get_referral_summary(db, user)


# 보관함 — 아직 쓰지 않은 무료 응모권
@router.get("/tickets", response_model=list[FreeTicketResponse])
def list_my_free_tickets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return referral_crud.get_unused_tickets(db, user.user_id)
