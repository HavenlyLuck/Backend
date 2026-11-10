# 찜한 상품 — 일반(결제) 상점 상품을 찜하고 마이페이지 "찜한 상품"에서 모아 본다
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.wishlist import WishlistItemResponse
from app.crud import wishlist as wishlist_crud

router = APIRouter()


@router.get("/me", response_model=list[WishlistItemResponse])
def get_my_wishlist(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [
        WishlistItemResponse(
            store_product_id=p.store_product_id,
            product_name=p.product_name,
            image_url=p.image_url,
            pay_type=p.pay_type,
            price=p.price,
            stock=p.stock,
            wished_at=w.created_at,
        )
        for w, p in wishlist_crud.get_wishlist(db, user.user_id)
    ]


# 찜하기 (이미 찜했으면 그대로)
@router.put("/{store_product_id}", status_code=204)
def add_to_wishlist(store_product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        wishlist_crud.add(db, user.user_id, store_product_id)
    except wishlist_crud.WishlistError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 찜 해제 (찜하지 않았어도 성공)
@router.delete("/{store_product_id}", status_code=204)
def remove_from_wishlist(store_product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wishlist_crud.remove(db, user.user_id, store_product_id)
