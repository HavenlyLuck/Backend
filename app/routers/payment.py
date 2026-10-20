# app/routers/payment.py — 응모권 · 쿠지 · 결제 상점 상품 카드 결제 (포트원 V2)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.raffle import RaffleEntry
from app.models.storage import StorageItem
from app.schemas.payment import (
    PaymentPrepareRequest, PaymentPrepareResponse, PaymentCustomer, PaymentCompleteResponse,
)
from app.schemas.raffle import RaffleEntryCreateResponse
from app.crud import payment as payment_crud
from app.crud import raffle as raffle_crud
from app.crud import kuji as kuji_crud
from app.crud import store as store_crud
from app.routers.kuji import validate_ticket_numbers, build_draw_response
from app.routers.store import store_purchase_response

router = APIRouter()


def _quantity(payload: PaymentPrepareRequest) -> int:
    if not payload.quantity or payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="수량은 1개 이상이어야 합니다")
    return payload.quantity


# 결제 주문 만들기 — 금액은 서버가 정한다. 지금 살 수 있는 상태인지 먼저 확인하고(결제 후 다시 확인한다)
@router.post("/prepare", response_model=PaymentPrepareResponse)
def prepare_payment(payload: PaymentPrepareRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ticket_numbers = None
    if payload.order_type == "raffle_entry":
        quantity = _quantity(payload)
        product = raffle_crud.get_raffle_product(db, payload.target_id)
        try:
            raffle_crud.check_can_enter(db, product, quantity)
        except raffle_crud.RaffleEntryError as e:
            raise HTTPException(status_code=400, detail=str(e))
        amount = product.ticket_price * quantity
        order_name = f"{product.product_name} 응모권 {quantity}장"

    elif payload.order_type == "kuji_draw":
        ticket_numbers = payload.ticket_numbers or []
        validate_ticket_numbers(ticket_numbers)
        try:
            kuji, _, conflicts = kuji_crud.check_tickets(db, payload.target_id, ticket_numbers)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except kuji_crud.KujiDrawError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if conflicts:
            return PaymentPrepareResponse(conflict_ticket_numbers=conflicts)
        quantity = len(ticket_numbers)
        amount = kuji.ticket_price * quantity
        order_name = f"{kuji.title} 쿠지 {quantity}장"

    else:
        quantity = _quantity(payload)
        product = store_crud.get_store_product(db, payload.target_id)
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
        if product.pay_type != "cash":
            raise HTTPException(status_code=400, detail="쌀포인트로 구매하는 상품입니다")
        if product.stock < quantity:
            raise HTTPException(status_code=400, detail="재고가 부족합니다")
        amount = product.price * quantity
        order_name = f"{product.product_name} {quantity}개"

    payment = payment_crud.create_payment(
        db,
        user_id=user.user_id,
        order_type=payload.order_type,
        target_id=payload.target_id,
        quantity=quantity,
        order_name=order_name,
        amount=amount,
        ticket_numbers=ticket_numbers,
    )
    return PaymentPrepareResponse(
        payment_id=payment.payment_id,
        order_name=payment.order_name,
        amount=payment.amount,
        customer=PaymentCustomer(full_name=user.name or user.nickname, phone_number=user.phone, email=user.email),
    )


# 결제 완료 — 결제창이 끝나면(PC 팝업 결과 / 모바일 리다이렉트) 프론트가 부른다. 여러 번 불러도 결과는 같다
@router.post("/{payment_id}/complete", response_model=PaymentCompleteResponse)
def complete_payment(payment_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        outcome = payment_crud.complete_payment(db, payment_id, user_id=user.user_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except payment_crud.PaymentError as e:
        raise HTTPException(status_code=502, detail=str(e))

    payment = payment_crud.get_payment(db, payment_id)
    status = "cancelled" if outcome["status"] == "cancel_requested" else outcome["status"]
    response = PaymentCompleteResponse(
        payment_id=payment_id, order_type=payment.order_type, status=status, message=outcome["message"],
    )

    if payment.order_type == "kuji_draw" and outcome["conflicts"]:
        kuji = kuji_crud.get_kuji_set(db, payment.target_id)
        response.kuji_draw = build_draw_response(db, kuji, [], outcome["conflicts"], False, 0)
    if status != "paid":
        return response

    if payment.order_type == "raffle_entry":
        entry = db.query(RaffleEntry).filter(RaffleEntry.payment_id == payment_id).first()
        entry.total_ticket_count = raffle_crud.get_user_total_ticket_count(db, entry.raffle_product_id, user.user_id)
        response.raffle_entry = RaffleEntryCreateResponse.model_validate(entry)
    elif payment.order_type == "kuji_draw":
        kuji, drawn, got_last_one = kuji_crud.get_paid_draw(
            db, payment.target_id, user.user_id, list(payment.ticket_numbers or []), payment_id,
        )
        response.kuji_draw = build_draw_response(db, kuji, drawn, [], got_last_one, payment.amount)
    else:
        item = db.query(StorageItem).filter(StorageItem.payment_id == payment_id).first()
        product = store_crud.get_store_product(db, payment.target_id)
        response.store_purchase = store_purchase_response(product, item)
    return response
