# app/routers/admin.py
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.crud import alimtalk as alimtalk_crud
from app.crud import ledger as ledger_crud
from app.database import get_db
from app.models.user import User
from app.schemas.admin import AlimtalkOverviewResponse, AlimtalkMessageResponse
from app.schemas.ledger import LedgerResponse
from app.services import alimtalk as alimtalk_service

router = APIRouter()


# 관리자 권한 검증 (프론트에서 /admin 진입 시 호출)
@router.get("/verify")
def verify_admin(admin: User = Depends(get_current_admin)):
    return {"is_admin": True}


# 알림톡 — 솔라피 설정 상태와 최근 발송 기록
@router.get("/alimtalk", response_model=AlimtalkOverviewResponse)
def get_alimtalk_overview(
    status: Optional[Literal["pending", "sending", "sent", "failed", "skipped"]] = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    return {
        "configured": alimtalk_service.is_configured(),
        "templates": [
            {"kind": kind, "label": alimtalk_service.KIND_LABELS[kind], "configured": bool(alimtalk_service.template_id(kind))}
            for kind in alimtalk_service.KINDS
        ],
        "counts": alimtalk_crud.count_by_status(db),
        "messages": alimtalk_crud.list_messages(db, status),
    }


# 실패했거나 보내지 않은 알림톡을 다시 보낸다 (10초 안에 나간다)
@router.post("/alimtalk/{message_id}/retry", response_model=AlimtalkMessageResponse)
def retry_alimtalk(message_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    try:
        alimtalk_crud.retry_message(db, message_id)
    except LookupError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except alimtalk_crud.AlimtalkRetryError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return alimtalk_crud.list_messages(db, None, message_id=message_id)[0]


# 주간 장부 — 기간(한국 날짜, 양 끝 포함)의 판매 · 물건 나감 · 회차 · 입고 · 비용 · 등록 상품 (개인정보 없이 user_id만)
@router.get("/ledger", response_model=LedgerResponse)
def get_ledger(
    start: date = Query(..., alias="from"),
    end: date = Query(..., alias="to"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if end < start:
        raise HTTPException(status_code=400, detail="기간이 올바르지 않습니다")
    if (end - start).days > 366:
        raise HTTPException(status_code=400, detail="한 번에 1년까지만 조회할 수 있습니다")
    return ledger_crud.get_ledger(db, start, end)
