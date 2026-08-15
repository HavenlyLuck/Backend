# app/routers/raffle.py
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Literal

from app.database import get_db
from app.core.dependencies import get_current_admin
from app.core.config import RAFFLE_TICKET_PRICE
from app.models.user import User
from app.schemas.raffle import RaffleProductResponse
from app.services.cloudinary import upload_image
from app.crud import raffle as raffle_crud

router = APIRouter()

# 라플 상품 등록 (관리자 전용) — 등록 시점부터 24시간 응모, 최대 응모권 수는 가격 ÷ 응모권가격으로 자동 계산
@router.post("", response_model=RaffleProductResponse)
def create_raffle_product(
    product_name: str = Form(...),
    description: Optional[str] = Form(None),
    price_krw: int = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if price_krw < RAFFLE_TICKET_PRICE:
        raise HTTPException(status_code=400, detail=f"가격은 응모권 가격({RAFFLE_TICKET_PRICE}원) 이상이어야 합니다")

    image_url = upload_image(image)
    return raffle_crud.create_raffle_product(
        db,
        admin_id=admin.user_id,
        product_name=product_name,
        description=description,
        price_krw=price_krw,
        image_url=image_url,
    )


# 라플 상품 목록 조회
@router.get("", response_model=list[RaffleProductResponse])
def list_raffle_products(
    status: Optional[Literal["open", "completed", "cancelled"]] = Query(None),
    db: Session = Depends(get_db),
):
    return raffle_crud.get_raffle_products(db, status=status)


# 라플 상품 상세 조회
@router.get("/{raffle_product_id}", response_model=RaffleProductResponse)
def get_raffle_product(raffle_product_id: int, db: Session = Depends(get_db)):
    product = raffle_crud.get_raffle_product(db, raffle_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
    return product
