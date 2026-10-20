# app/routers/store.py
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Literal

from app.database import get_db
from app.core.dependencies import get_current_admin, get_current_user
from app.models.user import User
from app.schemas.store import STORE_CATEGORIES, StoreCategory, StoreProductResponse, StorePurchaseRequest, StorePurchaseResponse
from app.services.cloudinary import upload_image
from app.crud import store as store_crud
from app.crud import point as point_crud

router = APIRouter()

# 상점 상품 등록 (관리자 전용) — 결제 상점(cash)/쌀포인트 상점(ssal) 중 하나를 지정해서 등록
@router.post("", response_model=StoreProductResponse)
def create_store_product(
    product_name: str = Form(...),
    description: Optional[str] = Form(None),
    pay_type: Literal["cash", "ssal"] = Form(...),
    category: StoreCategory = Form(...),
    price: int = Form(...),
    stock: int = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if price <= 0:
        raise HTTPException(status_code=400, detail="가격은 0보다 커야 합니다")
    if stock < 0:
        raise HTTPException(status_code=400, detail="재고는 0 이상이어야 합니다")
    if category not in STORE_CATEGORIES[pay_type]:
        raise HTTPException(status_code=400, detail="해당 상점에서 사용할 수 없는 분류입니다")

    image_url = upload_image(image, folder="store_products") if image else None
    return store_crud.create_store_product(
        db,
        admin_id=admin.user_id,
        product_name=product_name,
        description=description,
        pay_type=pay_type,
        category=category,
        price=price,
        stock=stock,
        image_url=image_url,
    )


# 상점 상품 목록 조회
@router.get("", response_model=list[StoreProductResponse])
def list_store_products(
    pay_type: Optional[Literal["cash", "ssal"]] = Query(None),
    db: Session = Depends(get_db),
):
    return store_crud.get_store_products(db, pay_type=pay_type)


# 상점 상품 상세 조회
@router.get("/{store_product_id}", response_model=StoreProductResponse)
def get_store_product(store_product_id: int, db: Session = Depends(get_db)):
    product = store_crud.get_store_product(db, store_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
    return product


# 쌀포인트 상점 구매 — 쌀포인트 차감, 재고 차감, 보관함 적재를 한 트랜잭션으로 처리
# (결제 상점 상품은 /payments 에서 카드 결제 후 지급한다)
@router.post("/{store_product_id}/purchase", response_model=StorePurchaseResponse)
def purchase_store_product(
    store_product_id: int,
    payload: StorePurchaseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = store_crud.get_store_product(db, store_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
    if product.pay_type != "ssal":
        raise HTTPException(status_code=400, detail="카드 결제로 구매하는 상품입니다")

    try:
        product, item = store_crud.fulfill_store_purchase(db, store_product_id, user.user_id, payload.quantity, "ssal")
        point_crud.apply_point_change(
            db,
            user_id=user.user_id,
            amount=-item.amount_spent,
            reason="store_purchase",
            reference_id=item.storage_item_id,
            description=f"{product.product_name} 구매 ({payload.quantity}개)",
        )
    except (store_crud.StorePurchaseError, ValueError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    return store_purchase_response(product, item)


def store_purchase_response(product, item) -> dict:
    return {
        "storage_item_id": item.storage_item_id,
        "store_product_id": product.store_product_id,
        "quantity": item.quantity,
        "amount_spent": item.amount_spent,
        "pay_type": product.pay_type,
        "remaining_stock": product.stock,
    }
