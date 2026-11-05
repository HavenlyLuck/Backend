from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.inquiry import Inquiry
from app.models.review import Review
from app.models.storage import StorageItem
from app.models.store import StoreProduct
from app.models.user import User
from app.crud import storage as storage_crud


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── 후기 ───────────────────────────────────────────

# 후기 작성자 — 가입 아이디의 가운데를 가린다 (abcdefg → ab****g). 원래 아이디는 응답에 넣지 않는다
def mask_login_id(login_id: str) -> str:
    n = len(login_id)
    if n <= 2:
        return login_id[:1] + "*" * (n - 1)
    if n <= 4:
        return login_id[0] + "*" * (n - 2) + login_id[-1]
    return login_id[:2] + "*" * (n - 3) + login_id[-1]


def _review_dict(review: Review, login_id: str, viewer_id: Optional[int], pay_type: Optional[str] = None) -> dict:
    return {
        "review_id": review.review_id,
        "rating": review.rating,
        "title": review.title,
        "content": review.content,
        "image_url": review.image_url,
        "product_name": review.product_name,
        "product_type": review.product_type,
        "pay_type": pay_type if review.product_type == "store" else None,
        "author": mask_login_id(login_id),
        "is_mine": viewer_id is not None and review.user_id == viewer_id,
        "created_at": review.created_at,
    }


def get_reviews(db: Session, viewer_id: Optional[int] = None) -> list[dict]:
    # 상점 후기는 일반 상점/쌀포인트 상점을 나눠 보여주려고 상품의 결제 방식을 붙인다
    rows = (
        db.query(Review, User.login_id, StoreProduct.pay_type)
        .join(User, Review.user_id == User.user_id)
        .outerjoin(StorageItem, Review.storage_item_id == StorageItem.storage_item_id)
        .outerjoin(StoreProduct, StorageItem.store_product_id == StoreProduct.store_product_id)
        .order_by(Review.created_at.desc(), Review.review_id.desc())
        .all()
    )
    return [_review_dict(r, login_id, viewer_id, pay_type) for r, login_id, pay_type in rows]


# 내 보관함 상품 중 아직 후기를 안 쓴 것
def get_reviewable_items(db: Session, user_id: int) -> list[dict]:
    reviewed = {
        sid for (sid,) in db.query(Review.storage_item_id)
        .filter(Review.user_id == user_id, Review.storage_item_id.isnot(None))
    }
    return [
        {
            "storage_item_id": item["storage_item_id"],
            "product_name": item["product_name"],
            "product_type": item["source"],
            "pay_type": item["pay_type"] if item["source"] == "store" else None,
            "image_url": item["image_url"],
            "created_at": item["created_at"],
        }
        for item in storage_crud.get_user_storage_items(db, user_id)
        if item["storage_item_id"] not in reviewed
    ]


class ReviewError(Exception):
    pass


def create_review(
    db: Session, user: User, storage_item_id: int, rating: int, title: str, content: str, image_url: Optional[str],
) -> dict:
    item = next(
        (i for i in storage_crud.get_user_storage_items(db, user.user_id) if i["storage_item_id"] == storage_item_id),
        None,
    )
    if not item:
        raise ReviewError("받은 상품에만 후기를 쓸 수 있어요")
    if db.query(Review).filter(Review.storage_item_id == storage_item_id).first():
        raise ReviewError("이미 후기를 쓴 상품이에요")
    review = Review(
        user_id=user.user_id,
        storage_item_id=storage_item_id,
        product_name=item["product_name"],
        product_type=item["source"],
        rating=rating,
        title=title,
        content=content,
        image_url=image_url,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return _review_dict(review, user.login_id, user.user_id, item["pay_type"])


def get_review(db: Session, review_id: int) -> Optional[Review]:
    return db.query(Review).filter(Review.review_id == review_id).first()


def delete_review(db: Session, review: Review) -> None:
    db.delete(review)
    db.commit()


# ── 문의 ───────────────────────────────────────────

def _inquiry_dict(q: Inquiry, nickname: str, viewer: Optional[User]) -> dict:
    mine = viewer is not None and q.user_id == viewer.user_id
    visible = not q.is_private or mine or (viewer is not None and viewer.is_admin)
    return {
        "inquiry_id": q.inquiry_id,
        "title": q.title if visible else "비공개 문의입니다",
        "content": q.content if visible else None,
        "is_private": q.is_private,
        "answer": q.answer if visible else None,
        "answered": q.answer is not None,
        "answered_at": q.answered_at,
        "nickname": nickname,
        "is_mine": mine,
        "created_at": q.created_at,
    }


# answered: None이면 전부, False면 답변대기만, True면 답변완료만
def get_inquiries(db: Session, viewer: Optional[User], answered: Optional[bool] = None) -> list[dict]:
    query = db.query(Inquiry, User.nickname).join(User, Inquiry.user_id == User.user_id)
    if answered is True:
        query = query.filter(Inquiry.answer.isnot(None))
    elif answered is False:
        query = query.filter(Inquiry.answer.is_(None))
    rows = query.order_by(Inquiry.created_at.desc(), Inquiry.inquiry_id.desc()).all()
    return [_inquiry_dict(q, nickname, viewer) for q, nickname in rows]


def create_inquiry(db: Session, user: User, title: str, content: str, is_private: bool) -> dict:
    q = Inquiry(user_id=user.user_id, title=title, content=content, is_private=is_private)
    db.add(q)
    db.commit()
    db.refresh(q)
    return _inquiry_dict(q, user.nickname, user)


def get_inquiry(db: Session, inquiry_id: int) -> Optional[Inquiry]:
    return db.query(Inquiry).filter(Inquiry.inquiry_id == inquiry_id).first()


def answer_inquiry(db: Session, q: Inquiry, admin: User, answer: str) -> dict:
    q.answer = answer
    q.admin_id = admin.user_id
    q.answered_at = _now()
    db.commit()
    db.refresh(q)
    nickname = db.query(User.nickname).filter(User.user_id == q.user_id).scalar() or ""
    return _inquiry_dict(q, nickname, admin)
