# app/routers/store.py
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Literal

from app.database import get_db
from app.core.dependencies import get_current_admin
from app.models.user import User
from app.schemas.store import StoreProductResponse
from app.services.cloudinary import upload_image
from app.crud import store as store_crud

router = APIRouter()

# 상점 상품 등록 (관리자 전용) — 운포인트/쌀포인트 상점 중 하나를 지정해서 등록
@router.post("", response_model=StoreProductResponse)
def create_store_product(
    product_name: str = Form(...),
    description: Optional[str] = Form(None),
    point_type: Literal["woon", "ssal"] = Form(...),
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

    image_url = upload_image(image, folder="store_products") if image else None
    return store_crud.create_store_product(
        db,
        admin_id=admin.user_id,
        product_name=product_name,
        description=description,
        point_type=point_type,
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
