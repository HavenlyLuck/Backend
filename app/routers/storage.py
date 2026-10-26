# app/routers/storage.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Literal
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.models.user import User
from app.schemas.storage import StorageItemResponse, ShippingRequest, AdminShippingItemResponse, AdminShipRequest
from app.crud import storage as storage_crud
from app.crud import address as address_crud
from app.crud import payment as payment_crud

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



# 보관함에서 상점 구매 취소 — 배송 신청 전인 카드 결제 상점 구매만 (쌀포인트 구매는 취소 불가)
@router.post("/{storage_item_id}/cancel", response_model=list[StorageItemResponse])
def cancel_store_purchase(
    storage_item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        payment_id = storage_crud.cancel_store_purchase(db, user.user_id, storage_item_id)
    except LookupError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except storage_crud.StorageCancelError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    # 포트원 환불이 지금 실패해도 cancel_requested로 남아 주기 작업이 다시 시도한다
    payment_crud.try_cancel_payment(db, payment_id)
    return storage_crud.get_user_storage_items(db, user.user_id)



# 관리자 배송 관리 — 배송 신청된(requested) / 발송 완료된(shipped) 보관함 상품, 오래 기다린 신청부터
@router.get("/admin", response_model=list[AdminShippingItemResponse])
def get_admin_shipping_items(
    status: Literal["requested", "shipped"] = Query("requested"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    return storage_crud.get_admin_shipping_items(db, status)


# 관리자 발송 처리 — 같은 박스로 보낸 상품들에 택배사 · 송장번호를 넣고 발송 완료로 바꾼다
@router.post("/admin/ship", response_model=list[AdminShippingItemResponse])
def mark_items_shipped(
    payload: AdminShipRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    ids = set(payload.storage_item_ids)
    carrier = payload.carrier.strip()
    tracking_number = payload.tracking_number.strip()
    if not ids:
        raise HTTPException(status_code=400, detail="발송 처리할 상품을 선택해주세요")
    if not carrier or not tracking_number:
        raise HTTPException(status_code=400, detail="택배사와 송장번호를 입력해주세요")

    items = storage_crud.get_items_for_update(db, list(ids))
    if len(items) != len(ids):
        db.rollback()
        raise HTTPException(status_code=404, detail="찾을 수 없는 상품이 포함되어 있습니다")
    if any(item.status != "requested" for item in items):
        db.rollback()
        raise HTTPException(status_code=400, detail="배송 신청 상태가 아닌 상품이 포함되어 있습니다")

    storage_crud.mark_shipped(db, items, carrier[:30], tracking_number[:50])
    return storage_crud.get_admin_shipping_items(db, "shipped")
