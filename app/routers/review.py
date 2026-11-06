# app/routers/review.py — 후기 (받은 상품에만 1개씩)
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_optional_user, log_admin_access
from app.crud import review as review_crud
from app.database import get_db
from app.models.user import User
from app.schemas.review import ReviewableItem, ReviewResponse
from app.services.cloudinary import upload_image, delete_image

router = APIRouter()


# 후기 목록 (누구나) — 최신순
@router.get("", response_model=list[ReviewResponse])
def list_reviews(db: Session = Depends(get_db), viewer: Optional[User] = Depends(get_optional_user)):
    return review_crud.get_reviews(db, viewer.user_id if viewer else None)


# 후기를 쓸 수 있는 내 상품 — 보관함에 받은 상품 중 아직 후기를 안 쓴 것
@router.get("/reviewable", response_model=list[ReviewableItem])
def list_reviewable_items(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return review_crud.get_reviewable_items(db, user.user_id)


# 후기 작성
@router.post("", response_model=ReviewResponse)
def create_review(
    storage_item_id: int = Form(...),
    rating: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    title, content = title.strip(), content.strip()
    if not 1 <= rating <= 5:
        raise HTTPException(status_code=400, detail="별점은 1~5점이에요")
    if not title or not content:
        raise HTTPException(status_code=400, detail="제목과 내용을 모두 입력해주세요")
    if len(title) > 200:
        raise HTTPException(status_code=400, detail="제목은 200자 이내로 입력해주세요")
    if image is not None and not (image.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="사진 파일만 올릴 수 있어요")

    # 사진은 상품 확인이 끝난 뒤에 올린다 (조건이 안 맞으면 업로드하지 않게)
    if storage_item_id not in {i["storage_item_id"] for i in review_crud.get_reviewable_items(db, user.user_id)}:
        raise HTTPException(status_code=400, detail="후기를 쓸 수 없는 상품이에요 (받은 상품에 한 번만 쓸 수 있어요)")
    image_url = upload_image(image, folder="reviews") if image else None
    try:
        return review_crud.create_review(db, user, storage_item_id, rating, title, content, image_url)
    except review_crud.ReviewError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# 후기 삭제 — 쓴 사람 또는 관리자
@router.delete("/{review_id}", status_code=204)
def delete_review(review_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    review = review_crud.get_review(db, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="후기를 찾을 수 없습니다")
    if review.user_id != user.user_id:
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="내가 쓴 후기만 지울 수 있어요")
        log_admin_access(user, request)   # 관리자가 남의 후기를 지우면 접속기록을 남긴다
    image_url = review.image_url
    review_crud.delete_review(db, review)
    if image_url:
        delete_image(image_url)   # DB에서 지운 뒤 사진 파일도 지운다
