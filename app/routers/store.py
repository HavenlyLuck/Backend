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
from app.crud import storage as storage_crud
from app.crud import point as point_crud

router = APIRouter()

# 상점 상품 등록 (관리자 전용) — 운포인트/쌀포인트 상점 중 하나를 지정해서 등록
@router.post("", response_model=StoreProductResponse)
def create_store_product(
    product_name: str = Form(...),
    description: Optional[str] = Form(None),
    point_type: Literal["woon", "ssal"] = Form(...),
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
    if category not in STORE_CATEGORIES[point_type]:
        raise HTTPException(status_code=400, detail="해당 상점에서 사용할 수 없는 분류입니다")

    image_url = upload_image(image, folder="store_products") if image else None
    return store_crud.create_store_product(
        db,
        admin_id=admin.user_id,
        product_name=product_name,
        description=description,
        point_type=point_type,
        category=category,
        price=price,
        stock=stock,
        image_url=image_url,
    )


# 상점 상품 목록 조회
@router.get("", response_model=list[StoreProductResponse])
def list_store_products(
    point_type: Optional[Literal["woon", "ssal"]] = Query(None),
    db: Session = Depends(get_db),
):
    return store_crud.get_store_products(db, point_type=point_type)


# 상점 상품 상세 조회
@router.get("/{store_product_id}", response_model=StoreProductResponse)
def get_store_product(store_product_id: int, db: Session = Depends(get_db)):
    product = store_crud.get_store_product(db, store_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
    return product


# 상점 상품 구매 — 포인트 차감, 재고 차감, 보관함 적재를 한 트랜잭션으로 처리
@router.post("/{store_product_id}/purchase", response_model=StorePurchaseResponse)
def purchase_store_product(
    store_product_id: int,
    payload: StorePurchaseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="구매 수량은 1개 이상이어야 합니다")

    product = store_crud.get_store_product_for_update(db, store_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
    if product.stock < payload.quantity:
        db.rollback()
        raise HTTPException(status_code=400, detail="재고가 부족합니다")

    points_spent = product.price * payload.quantity
    product.stock -= payload.quantity
    item = storage_crud.add_store_purchase(
        db,
        user_id=user.user_id,
        store_product_id=product.store_product_id,
        quantity=payload.quantity,
        points_spent=points_spent,
    )

    try:
        point_crud.apply_point_change(
            db,
            user_id=user.user_id,
            point_type=product.point_type,
            amount=-points_spent,
            reason="store_purchase",
            reference_id=item.storage_item_id,
            description=f"{product.product_name} 구매 ({payload.quantity}개)",
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    return {
        "storage_item_id": item.storage_item_id,
        "store_product_id": product.store_product_id,
        "quantity": payload.quantity,
        "points_spent": points_spent,
        "point_type": product.point_type,
        "remaining_stock": product.stock,
    }
