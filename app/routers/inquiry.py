# app/routers/inquiry.py — 문의 (비공개 문의는 쓴 사람과 관리자만 내용을 본다)
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin, get_current_user, get_optional_user
from app.crud import review as review_crud
from app.database import get_db
from app.models.user import User
from app.schemas.review import InquiryAnswer, InquiryCreate, InquiryResponse

router = APIRouter()


# 문의 목록 (누구나) — 최신순
@router.get("", response_model=list[InquiryResponse])
def list_inquiries(db: Session = Depends(get_db), viewer: Optional[User] = Depends(get_optional_user)):
    return review_crud.get_inquiries(db, viewer)


# 문의 작성 (로그인 필요)
@router.post("", response_model=InquiryResponse)
def create_inquiry(body: InquiryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    title, content = body.title.strip(), body.content.strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="제목과 내용을 모두 입력해주세요")
    if len(title) > 200:
        raise HTTPException(status_code=400, detail="제목은 200자 이내로 입력해주세요")
    return review_crud.create_inquiry(db, user, title, content, body.is_private)


# 관리자 문의 목록 — answered=false면 답변대기만
@router.get("/admin", response_model=list[InquiryResponse])
def list_inquiries_admin(
    answered: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    return review_crud.get_inquiries(db, admin, answered)


# 답변 작성·수정 (관리자)
@router.put("/{inquiry_id}/answer", response_model=InquiryResponse)
def answer_inquiry(inquiry_id: int, body: InquiryAnswer, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    answer = body.answer.strip()
    if not answer:
        raise HTTPException(status_code=400, detail="답변 내용을 입력해주세요")
    q = review_crud.get_inquiry(db, inquiry_id)
    if not q:
        raise HTTPException(status_code=404, detail="문의를 찾을 수 없습니다")
    return review_crud.answer_inquiry(db, q, admin, answer)
