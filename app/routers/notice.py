# app/routers/notice.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_admin
from app.models.user import User
from app.schemas.notice import NoticeCreate, NoticeResponse, NoticeUpdate
from app.crud import notice as notice_crud

router = APIRouter()

# 공지사항 목록 (누구나) — 고정글 먼저, 최신순
@router.get("", response_model=list[NoticeResponse])
def list_notices(db: Session = Depends(get_db)):
    return notice_crud.get_notices(db)


# 공지사항 작성 (관리자 전용)
@router.post("", response_model=NoticeResponse)
def create_notice(body: NoticeCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    title, content = body.title.strip(), body.content.strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="제목과 내용을 모두 입력해주세요")
    return notice_crud.create_notice(db, admin_id=admin.user_id, title=title, content=content, pinned=body.pinned)


# 공지사항 수정·고정 (관리자 전용)
@router.patch("/{notice_id}", response_model=NoticeResponse)
def update_notice(notice_id: int, body: NoticeUpdate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    notice = notice_crud.get_notice(db, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다")
    changes = body.model_dump(exclude_none=True)
    for key in ("title", "content"):
        if key in changes:
            changes[key] = changes[key].strip()
            if not changes[key]:
                raise HTTPException(status_code=400, detail="제목과 내용을 모두 입력해주세요")
    return notice_crud.update_notice(db, notice, changes)


# 공지사항 삭제 (관리자 전용)
@router.delete("/{notice_id}", status_code=204)
def delete_notice(notice_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    notice = notice_crud.get_notice(db, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다")
    notice_crud.delete_notice(db, notice)
