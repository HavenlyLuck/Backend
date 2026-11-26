# app/routers/idea_contest.py — 천운 아바타 아이디어 공모전 (컨텐츠)
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin, get_current_user, get_optional_user
from app.crud import idea_contest as crud
from app.database import get_db
from app.models.user import User
from app.schemas.idea_contest import (
    IdeaAdminEntryResponse, IdeaAdminWeek, IdeaAwardRequest, IdeaContestCurrentResponse, IdeaEntryResponse, IdeaHideRequest,
    IdeaLikeResponse,
)
from app.services.cloudinary import delete_image, upload_image

router = APIRouter()

MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 그림판 PNG — 800×800이라 보통 수백 KB


def _public(row: dict, viewer: Optional[User]) -> dict:
    return {**row, "mine": bool(viewer and row["user_id"] == viewer.user_id)}


# 이번 주 공모전 — 응모작(최신순) · 상품 · 내가 올린 수 · 최근 수상작
@router.get("/current", response_model=IdeaContestCurrentResponse)
def get_current(db: Session = Depends(get_db), viewer: Optional[User] = Depends(get_optional_user)):
    week = crud.current_week()
    starts_at, ends_at = crud.week_bounds(week)
    viewer_id = viewer.user_id if viewer else None
    return {
        "week_start": week,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "prizes": [{"rank": r, "ssal_ticket": n} for r, n in crud.PRIZES.items()],
        "max_entries_per_week": crud.MAX_ENTRIES_PER_WEEK,
        "my_entry_count": crud.count_my_entries(db, viewer.user_id, week) if viewer else 0,
        "entries": [_public(r, viewer) for r in crud.list_week(db, week, viewer_id=viewer_id)],
        "recent_winners": [
            {"week_start": w["week_start"], "winners": [_public(r, viewer) for r in w["winners"]]}
            for w in crud.recent_winners(db, viewer_id=viewer_id)
        ],
    }


# 응모 — 아바타 분류 + 그림판에서 그린 PNG 1장 + 아이디어 이름(40자) + 설명(300자, 선택). 한 사람이 한 주에 1개
@router.post("/entries", response_model=IdeaEntryResponse, status_code=201)
def create_entry(
    category: str = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if category not in crud.CATEGORIES:
        raise HTTPException(status_code=400, detail="아바타 분류를 골라주세요")
    title = title.strip()
    description = (description or "").strip() or None
    if not title:
        raise HTTPException(status_code=400, detail="아이디어 이름을 입력해주세요")
    if len(title) > 40:
        raise HTTPException(status_code=400, detail="아이디어 이름은 40자 이내로 입력해주세요")
    if description and len(description) > 300:
        raise HTTPException(status_code=400, detail="설명은 300자 이내로 입력해주세요")
    # 그림판은 PNG로만 내보낸다 — 사진(JPEG 등)은 받지 않는다
    if image.content_type != "image/png":
        raise HTTPException(status_code=400, detail="그림판에서 그린 그림만 올릴 수 있어요")
    if image.size is not None and image.size > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="그림 파일이 너무 커요")
    # 한도를 넘었으면 사진을 올리기 전에 막는다
    try:
        crud.check_can_enter(db, user.user_id)
    except crud.IdeaContestError as e:
        raise HTTPException(status_code=400, detail=str(e))

    image_url = upload_image(image, folder="idea_contest")
    try:
        row = crud.create_entry(db, user.user_id, category, title, description, image_url)
    except crud.IdeaContestError as e:
        db.rollback()
        delete_image(image_url)
        raise HTTPException(status_code=400, detail=str(e))
    return _public(row, user)


# 내 응모작 지우기 — 이번 주 응모작만
@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entry = crud.get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="응모작을 찾을 수 없어요")
    try:
        image_url = crud.delete_my_entry(db, entry, user.user_id)
    except crud.IdeaContestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    delete_image(image_url)


# 좋아요 — 한 계정이 한 응모작에 한 번 (이번 주 응모작만, 내 응모작 제외)
@router.post("/entries/{entry_id}/like", response_model=IdeaLikeResponse)
def like_entry(entry_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _set_like(db, entry_id, user, True)


# 좋아요 취소
@router.delete("/entries/{entry_id}/like", response_model=IdeaLikeResponse)
def unlike_entry(entry_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _set_like(db, entry_id, user, False)


def _set_like(db: Session, entry_id: int, user: User, like: bool) -> dict:
    entry = crud.get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="응모작을 찾을 수 없어요")
    try:
        count, liked = crud.set_like(db, entry, user.user_id, like)
    except crud.IdeaContestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"entry_id": entry_id, "like_count": count, "liked": liked}


# ── 관리자 ──

# 응모작이 있었던 주 목록 (이번 주 포함, 최근 주부터)
@router.get("/admin/weeks", response_model=list[IdeaAdminWeek])
def admin_weeks(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return crud.admin_weeks(db)


# 그 주의 응모작 전부 (가린 것 포함)
@router.get("/admin/weeks/{week_start}", response_model=list[IdeaAdminEntryResponse])
def admin_week_entries(week_start: date, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return crud.list_week(db, week_start, include_hidden=True)


# 시상 — 끝난 주에서 1등부터 차례로 고른 응모작에 등수를 매기고 쌀 응모권 지급 (1등 10장, 2등 7장, 3등 5장)
@router.post("/admin/weeks/{week_start}/award", response_model=list[IdeaAdminEntryResponse])
def admin_award(
    week_start: date,
    payload: IdeaAwardRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    try:
        crud.award_week(db, week_start, payload.entry_ids, admin.user_id)
    except crud.IdeaContestError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return crud.list_week(db, week_start, include_hidden=True)


# 부적절한 응모작 가리기 / 다시 보이기
@router.post("/admin/entries/{entry_id}/hide", response_model=IdeaAdminEntryResponse)
def admin_hide(
    entry_id: int,
    payload: IdeaHideRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    entry = crud.get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="응모작을 찾을 수 없어요")
    try:
        crud.set_hidden(db, entry, payload.hidden)
    except crud.IdeaContestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return crud.get_entry_dict(db, entry_id)
