# app/routers/storage.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.storage import StorageItemResponse, ShippingRequest
from app.crud import storage as storage_crud
from app.crud import address as address_crud

router = APIRouter()

# 내 보관함 — 당첨된 응모 상품과 상점에서 구매한 상품
@router.get("/me", response_model=list[StorageItemResponse])
def get_my_storage(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return storage_crud.get_user_storage_items(db, user.user_id)


# 선택한 보관함 상품 배송 신청 — 보관 중(ready)인 내 상품만 신청 가능
@router.post("/ship", response_model=list[StorageItemResponse])
def request_shipping(
    payload: ShippingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ids = set(payload.storage_item_ids)
    if not ids:
        raise HTTPException(status_code=400, detail="배송 신청할 상품을 선택해주세요")

    if not address_crud.get_user_address(db, user.user_id, payload.address_id):
        raise HTTPException(status_code=404, detail="배송지를 찾을 수 없습니다")

    items = storage_crud.get_user_items_for_update(db, user.user_id, list(ids))
    if len(items) != len(ids):
        db.rollback()
        raise HTTPException(status_code=404, detail="보관함에 없는 상품이 포함되어 있습니다")
    if any(item.status != "ready" for item in items):
        db.rollback()
        raise HTTPException(status_code=400, detail="이미 배송 신청된 상품이 포함되어 있습니다")

    storage_crud.request_shipping(db, items, payload.address_id)
    return storage_crud.get_user_storage_items(db, user.user_id)
