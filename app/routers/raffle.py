# app/routers/raffle.py
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, Literal

from app.database import get_db
from app.core.dependencies import get_current_admin, get_current_user
from app.core.config import RAFFLE_TICKET_PRICE
from app.models.user import User
from app.schemas.raffle import RaffleProductResponse, RaffleEntryCreate, RaffleEntryResponse
from app.services.cloudinary import upload_image
from app.crud import raffle as raffle_crud
from app.crud import point as point_crud

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
    products = raffle_crud.get_raffle_products(db, status=status)
    sold_map = raffle_crud.get_sold_ticket_counts(db, [p.raffle_product_id for p in products])
    for p in products:
        p.sold_slots = sold_map.get(p.raffle_product_id, 0)
    return products


# 라플 상품 상세 조회
@router.get("/{raffle_product_id}", response_model=RaffleProductResponse)
def get_raffle_product(raffle_product_id: int, db: Session = Depends(get_db)):
    product = raffle_crud.get_raffle_product(db, raffle_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
    product.sold_slots = raffle_crud.get_sold_ticket_count(db, raffle_product_id)
    return product


# 응모 참여 — 운포인트를 차감하고 응모권을 발급한다
@router.post("/{raffle_product_id}/entries", response_model=RaffleEntryResponse)
def create_raffle_entry(
    raffle_product_id: int,
    payload: RaffleEntryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.ticket_count <= 0:
        raise HTTPException(status_code=400, detail="응모권 수는 1장 이상이어야 합니다")

    # 행 잠금으로 조회 → 동시 응모 시에도 total_slots를 넘겨 팔지 않도록 보장
    product = raffle_crud.get_raffle_product_for_update(db, raffle_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if product.status != "open" or product.ends_at <= now:
        raise HTTPException(status_code=400, detail="마감된 응모입니다")

    sold = raffle_crud.get_sold_ticket_count(db, raffle_product_id)
    if sold + payload.ticket_count > product.total_slots:
        raise HTTPException(status_code=400, detail="남은 응모권이 부족합니다")

    entry = raffle_crud.create_raffle_entry(
        db,
        raffle_product_id=raffle_product_id,
        user_id=user.user_id,
        ticket_count=payload.ticket_count,
        points_spent=payload.ticket_count * product.ticket_price,
    )

    try:
        point_crud.apply_point_change(
            db,
            user_id=user.user_id,
            point_type="woon",
            amount=-entry.points_spent,
            reason="raffle_entry",
            reference_id=entry.entry_id,
            description=f"{product.product_name} 응모 ({payload.ticket_count}장)",
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(entry)
    return entry


# 특정 응모 상품에 대한 내 응모 내역
@router.get("/{raffle_product_id}/entries/me", response_model=list[RaffleEntryResponse])
def get_my_raffle_entries(
    raffle_product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return raffle_crud.get_user_raffle_entries(db, raffle_product_id, user.user_id)
