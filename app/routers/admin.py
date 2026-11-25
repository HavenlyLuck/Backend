# app/routers/admin.py
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.crud import alimtalk as alimtalk_crud
from app.database import get_db
from app.models.user import User
from app.schemas.admin import AlimtalkOverviewResponse, AlimtalkMessageResponse
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
