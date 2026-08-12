# app/routers/raffle.py
from fastapi import APIRouter, Depends, Form, File, UploadFile
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.core.dependencies import get_current_admin
from app.models.user import User
from app.schemas.raffle import RaffleProductResponse
from app.services.cloudinary import upload_image
from app.crud import raffle as raffle_crud

router = APIRouter()

# 라플 상품 등록 (관리자 전용)
@router.post("", response_model=RaffleProductResponse)
def create_raffle_product(
    product_name: str = Form(...),
    description: Optional[str] = Form(None),
    price_krw: int = Form(...),
    ticket_price: int = Form(...),
    total_slots: int = Form(...),
    starts_at: datetime = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    image_url = upload_image(image)
    return raffle_crud.create_raffle_product(
        db,
        admin_id=admin.user_id,
        product_name=product_name,
        description=description,
        price_krw=price_krw,
        ticket_price=ticket_price,
        total_slots=total_slots,
        image_url=image_url,
        starts_at=starts_at,
    )
