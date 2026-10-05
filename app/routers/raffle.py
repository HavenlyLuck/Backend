# app/routers/raffle.py
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, Literal

from app.database import get_db
from app.core.dependencies import get_current_admin, get_current_user
from app.core.config import RAFFLE_TICKET_PRICE, RAFFLE_DURATION_DAYS_OPTIONS
from app.models.user import User
from app.schemas.raffle import (
    RaffleProductResponse, RaffleEntryCreate, RaffleEntryResponse,
    RaffleEntryCreateResponse, MyRaffleEntryResponse, RaffleEntrantResponse,
    RaffleDrawCastResponse,
)
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
    duration_days: int = Form(1),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if price_krw < RAFFLE_TICKET_PRICE:
        raise HTTPException(status_code=400, detail=f"가격은 응모권 가격({RAFFLE_TICKET_PRICE}원) 이상이어야 합니다")
    if duration_days not in RAFFLE_DURATION_DAYS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"응모 기간은 {', '.join(map(str, RAFFLE_DURATION_DAYS_OPTIONS))}일 중에서 선택해야 합니다")

    image_url = upload_image(image)
    return raffle_crud.create_raffle_product(
        db,
        admin_id=admin.user_id,
        product_name=product_name,
        description=description,
        price_krw=price_krw,
        image_url=image_url,
        duration_days=duration_days,
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


# 마감됐지만 아직 추첨하지 않은 상품 목록 (관리자 추첨 화면용) — {raffle_product_id}보다 먼저 등록해야 경로가 겹치지 않는다
@router.get("/pending-draw", response_model=list[RaffleProductResponse])
def list_pending_draw_products(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    products = raffle_crud.get_closed_undrawn_products(db)
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
@router.post("/{raffle_product_id}/entries", response_model=RaffleEntryCreateResponse)
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

    # 이미 이 상품에 응모한 적이 있으면 그 번호를 그대로 쓰고, 처음이면 새 번호를 부여한다
    entry_number = raffle_crud.get_existing_entry_number(db, raffle_product_id, user.user_id)
    if entry_number is None:
        entry_number = raffle_crud.get_next_entry_number(db, raffle_product_id)

    entry = raffle_crud.create_raffle_entry(
        db,
        raffle_product_id=raffle_product_id,
        user_id=user.user_id,
        ticket_count=payload.ticket_count,
        points_spent=payload.ticket_count * product.ticket_price,
        entry_number=entry_number,
    )

    # 이번 구매로 매진됐으면 매진 시각을 남긴다 — 이 시각부터 RAFFLE_DRAW_DELAY_SECONDS 뒤에 자동 추첨
    if sold + payload.ticket_count >= product.total_slots:
        product.sold_out_at = now

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
    entry.total_ticket_count = raffle_crud.get_user_total_ticket_count(db, raffle_product_id, user.user_id)
    return entry


# 특정 응모 상품에 대한 내 응모 내역
@router.get("/{raffle_product_id}/entries/me", response_model=list[RaffleEntryResponse])
def get_my_raffle_entries(
    raffle_product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return raffle_crud.get_user_raffle_entries(db, raffle_product_id, user.user_id)


# 마이페이지 응모 내역 — 전체 상품에 걸친 내 응모 내역
@router.get("/entries/me", response_model=list[MyRaffleEntryResponse])
def get_my_raffle_entries_all(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return raffle_crud.get_user_raffle_entries_all(db, user.user_id)


# 추첨 룰렛 구슬 배치용 — 응모 번호별 총 응모권 수 (관리자 전용)
@router.get("/{raffle_product_id}/entrants", response_model=list[RaffleEntrantResponse])
def get_raffle_entrants(
    raffle_product_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    entrants = raffle_crud.get_entrants(db, raffle_product_id)
    return [{"entry_number": n, "ticket_count": c} for n, c in entrants]


# 번개 추첨 화면용 응모자 목록 — 매진 후(추첨 대기 5분 동안 미리 받아두거나 추첨 후 결과를 볼 때)
# 이 상품에 응모한 사람(또는 관리자)만 볼 수 있고, 당첨 번호는 추첨이 끝난 뒤에만 내려간다
@router.get("/{raffle_product_id}/draw-cast", response_model=RaffleDrawCastResponse)
def get_raffle_draw_cast(
    raffle_product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = raffle_crud.get_raffle_product(db, raffle_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
    if not user.is_admin and not raffle_crud.has_entered(db, raffle_product_id, user.user_id):
        raise HTTPException(status_code=403, detail="이 응모에 참여한 사람만 볼 수 있습니다")
    if product.sold_out_at is None and product.status != "completed":
        raise HTTPException(status_code=400, detail="아직 응모권이 매진되지 않았습니다")

    return {
        "raffle_product_id": product.raffle_product_id,
        "sold_out_at": product.sold_out_at,
        "draw_at": raffle_crud.get_draw_at(product),
        "winner_entry_number": product.winner_entry_number,
        "cast": raffle_crud.get_draw_cast(db, raffle_product_id),
    }
