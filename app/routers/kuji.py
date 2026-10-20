# app/routers/kuji.py
import json
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, Query
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session
from typing import Optional, Literal

from app.database import get_db
from app.core.config import KUJI_TICKET_PRICE, KUJI_MAX_TICKETS, KUJI_MAX_DRAW
from app.core.dependencies import get_current_admin
from app.models.user import User
from app.schemas.kuji import (
    KujiPrizeCreate, KujiSetResponse, KujiSetAdminResponse, KujiBoardResponse, KujiDrawnTicket,
    KujiDrawResponse, KujiDrawnPrize, KujiLastOnePrize,
)
from app.services.cloudinary import upload_image
from app.crud import kuji as kuji_crud

router = APIRouter()

_prize_list = TypeAdapter(list[KujiPrizeCreate])


# 쿠지 한 판 등록 (관리자 전용)
# prizes는 JSON 문자열 — [{"tier": "upper"|"lower", "name", "quantity", "cost", "image_index"}]
# 상품 사진은 prize_images로 여러 장 올리고, 각 상품의 image_index로 몇 번째 파일인지 가리킨다
@router.post("", response_model=KujiSetAdminResponse)
def create_kuji_set(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    ticket_price: int = Form(KUJI_TICKET_PRICE),
    prizes: str = Form(...),
    image: UploadFile = File(...),
    prize_images: list[UploadFile] = File([]),
    last_one_name: Optional[str] = Form(None),
    last_one_cost: Optional[int] = Form(None),
    last_one_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="쿠지 이름을 입력해주세요")
    if ticket_price <= 0:
        raise HTTPException(status_code=400, detail="1장 가격은 0보다 커야 합니다")

    try:
        items = _prize_list.validate_python(json.loads(prizes))
    except (json.JSONDecodeError, ValidationError):
        raise HTTPException(status_code=400, detail="상품 구성 형식이 올바르지 않습니다")

    for it in items:
        it.name = it.name.strip()
        if not it.name:
            raise HTTPException(status_code=400, detail="상품명을 모두 입력해주세요")
        if it.quantity <= 0:
            raise HTTPException(status_code=400, detail="상품 개수는 1개 이상이어야 합니다")
        if it.cost < 0:
            raise HTTPException(status_code=400, detail="원가는 0 이상이어야 합니다")
        if it.image_index is not None and not 0 <= it.image_index < len(prize_images):
            raise HTTPException(status_code=400, detail="상품 사진 번호가 올바르지 않습니다")
    # 등급은 상위상 → 하위상 순서로 A, B, … 를 매긴다
    items.sort(key=lambda it: 0 if it.tier == "upper" else 1)
    if not any(it.tier == "upper" for it in items) or not any(it.tier == "lower" for it in items):
        raise HTTPException(status_code=400, detail="상위상과 하위상을 각각 하나 이상 넣어주세요")
    if len(items) > 26:
        raise HTTPException(status_code=400, detail="상품은 26개(A~Z상)까지 넣을 수 있습니다")
    total = sum(it.quantity for it in items)
    if total > KUJI_MAX_TICKETS:
        raise HTTPException(status_code=400, detail=f"제비는 한 판에 {KUJI_MAX_TICKETS}장까지 만들 수 있습니다")

    last_one_name = (last_one_name or "").strip() or None
    if not last_one_name and (last_one_cost or last_one_image):
        raise HTTPException(status_code=400, detail="라스트원상 이름을 입력해주세요")
    if last_one_cost is not None and last_one_cost < 0:
        raise HTTPException(status_code=400, detail="라스트원상 원가는 0 이상이어야 합니다")

    # 사진은 쓰이는 것만 올린다
    image_url = upload_image(image, folder="kuji_sets")
    uploaded: dict[int, str] = {}
    for it in items:
        if it.image_index is not None and it.image_index not in uploaded:
            uploaded[it.image_index] = upload_image(prize_images[it.image_index], folder="kuji_prizes")
    last_one_image_url = upload_image(last_one_image, folder="kuji_prizes") if last_one_name and last_one_image else None

    return kuji_crud.create_kuji_set(
        db,
        admin_id=admin.user_id,
        title=title,
        description=description,
        image_url=image_url,
        ticket_price=ticket_price,
        prizes=[
            {
                "tier": it.tier,
                "name": it.name,
                "quantity": it.quantity,
                "cost": it.cost,
                "image_url": uploaded.get(it.image_index) if it.image_index is not None else None,
            }
            for it in items
        ],
        last_one_name=last_one_name,
        last_one_image_url=last_one_image_url,
        last_one_cost=(last_one_cost or 0) if last_one_name else None,
    )


# 관리자용 쿠지 목록 — 원가·예상 매출 포함
@router.get("/admin", response_model=list[KujiSetAdminResponse])
def list_kuji_sets_admin(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    return kuji_crud.get_kuji_sets(db)


# 쿠지 목록
@router.get("", response_model=list[KujiSetResponse])
def list_kuji_sets(
    status: Optional[Literal["open", "sold_out", "closed"]] = Query(None),
    db: Session = Depends(get_db),
):
    return kuji_crud.get_kuji_sets(db, status=status)


# 쿠지 상세
@router.get("/{kuji_set_id}", response_model=KujiSetResponse)
def get_kuji_set(kuji_set_id: int, db: Session = Depends(get_db)):
    kuji = kuji_crud.get_kuji_set(db, kuji_set_id)
    if not kuji:
        raise HTTPException(status_code=404, detail="쿠지를 찾을 수 없습니다")
    return kuji


def build_board(db: Session, kuji) -> KujiBoardResponse:
    return KujiBoardResponse(
        kuji_set_id=kuji.kuji_set_id,
        version=kuji.board_version,
        total_tickets=kuji.total_tickets,
        remaining_tickets=kuji.remaining_tickets,
        drawn=[KujiDrawnTicket(ticket_number=n, grade=g) for n, g in kuji_crud.get_drawn_tickets(db, kuji.kuji_set_id)],
    )


# 제비판 — 뽑힌 제비의 번호·등급만. since가 지금 버전과 같으면 바뀐 게 없으니 null
@router.get("/{kuji_set_id}/board", response_model=Optional[KujiBoardResponse])
def get_kuji_board(kuji_set_id: int, since: Optional[int] = Query(None), db: Session = Depends(get_db)):
    kuji = kuji_crud.get_kuji_set(db, kuji_set_id)
    if not kuji:
        raise HTTPException(status_code=404, detail="쿠지를 찾을 수 없습니다")
    if since is not None and since == kuji.board_version:
        return None
    return build_board(db, kuji)


# 쿠지 뽑기(제비 결제)는 /payments 에서 처리한다 (app/routers/payment.py)
def validate_ticket_numbers(numbers: list[int]) -> None:
    if not numbers:
        raise HTTPException(status_code=400, detail="뽑을 제비를 골라주세요")
    if len(numbers) > KUJI_MAX_DRAW:
        raise HTTPException(status_code=400, detail=f"한 번에 {KUJI_MAX_DRAW}장까지 뽑을 수 있습니다")
    if len(set(numbers)) != len(numbers):
        raise HTTPException(status_code=400, detail="같은 제비를 두 번 고를 수 없습니다")


def build_draw_response(db: Session, kuji, drawn, conflicts: list[int], got_last_one: bool, amount_paid: int) -> KujiDrawResponse:
    return KujiDrawResponse(
        ok=not conflicts,
        drawn=[
            KujiDrawnPrize(
                ticket_number=t.ticket_number, kuji_prize_id=p.kuji_prize_id, grade=p.grade,
                tier=p.tier, name=p.name, image_url=p.image_url,
            )
            for t, p in drawn
        ],
        last_one=KujiLastOnePrize(name=kuji.last_one_name, image_url=kuji.last_one_image_url) if got_last_one else None,
        amount_paid=amount_paid,
        conflict_ticket_numbers=conflicts,
        board=build_board(db, kuji),
    )
