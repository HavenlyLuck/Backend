# app/routers/payment.py — 응모권 · 쿠지 · 결제 상점 상품 · 배송비 카드 결제 (포트원 V2)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.raffle import RaffleEntry
from app.models.storage import StorageItem
from app.schemas.payment import (
    PaymentPrepareRequest, PaymentPrepareResponse, PaymentCustomer, PaymentCompleteResponse, MyPaymentResponse,
)
from app.schemas.raffle import RaffleEntryCreateResponse
from app.schemas.storage import StorageItemResponse
from app.schemas.store import StorePurchaseResponse
from app.crud import payment as payment_crud
from app.crud import raffle as raffle_crud
from app.crud import kuji as kuji_crud
from app.crud import store as store_crud
from app.crud import storage as storage_crud
from app.crud import point as point_crud
from app.routers.kuji import validate_ticket_numbers, build_draw_response
from app.routers.store import store_purchase_response
from app.core.config import RAFFLE_TICKET_PRICE, SHIPPING_FEE, STORE_POINT_DISCOUNT_RATE_PERCENT

router = APIRouter()


# 결제 상점 구매 금액에서 쌀포인트로 할인받을 수 있는 최대치 (원 단위 내림)
def max_store_point_discount(total: int) -> int:
    return total * STORE_POINT_DISCOUNT_RATE_PERCENT // 100


def _quantity(payload: PaymentPrepareRequest) -> int:
    if not payload.quantity or payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="수량은 1개 이상이어야 합니다")
    return payload.quantity


# 마이페이지 구매 내역 — 내 카드 결제(응모권 · 쿠지 · 결제 상점 · 배송비), 환불된 것 포함, 최신순
@router.get("/me", response_model=list[MyPaymentResponse])
def list_my_payments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return payment_crud.get_my_payments(db, user.user_id)


# 결제 주문 만들기 — 금액은 서버가 정한다. 지금 살 수 있는 상태인지 먼저 확인하고(결제 후 다시 확인한다)
@router.post("/prepare", response_model=PaymentPrepareResponse)
def prepare_payment(payload: PaymentPrepareRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ticket_numbers = None
    storage_item_ids = None
    point_used = 0
    if payload.point_use and payload.order_type != "store_purchase":
        raise HTTPException(status_code=400, detail="쌀포인트 할인은 상점 상품 구매에만 쓸 수 있습니다")
    if payload.order_type == "raffle_entry":
        quantity = _quantity(payload)
        product = raffle_crud.get_raffle_product(db, payload.target_id)
        try:
            raffle_crud.check_can_enter(db, product, quantity)
        except raffle_crud.RaffleEntryError as e:
            raise HTTPException(status_code=400, detail=str(e))
        amount = product.ticket_price * quantity
        order_name = f"{product.product_name} 응모권 {quantity}장"

    elif payload.order_type == "store_funding":
        # 상점 상품 → 응모 전환 모금 응모권 (target_id = 상점 상품 id)
        quantity = _quantity(payload)
        store_product = store_crud.get_store_product(db, payload.target_id)
        try:
            raffle_crud.check_can_fund(db, store_product, quantity, user)
        except raffle_crud.RaffleEntryError as e:
            raise HTTPException(status_code=400, detail=str(e))
        amount = RAFFLE_TICKET_PRICE * quantity
        order_name = f"{store_product.product_name} 응모 전환 응모권 {quantity}장"

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

    elif payload.order_type == "shipping_fee":
        # 보관함 상품 배송 신청 — 한 번에 신청한 상품은 한 박스라 배송비는 1번 (target_id = 배송지)
        storage_item_ids = sorted(set(payload.storage_item_ids or []))
        try:
            quantity = storage_crud.check_can_request_shipping(db, user.user_id, storage_item_ids, payload.target_id)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except storage_crud.ShippingRequestError as e:
            raise HTTPException(status_code=400, detail=str(e))
        amount = SHIPPING_FEE
        order_name = f"배송비 · 상품 {quantity}개"

    else:
        quantity = _quantity(payload)
        product = store_crud.get_store_product(db, payload.target_id)
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
        if product.pay_type != "cash":
            raise HTTPException(status_code=400, detail="쌀포인트로 구매하는 상품입니다")
        if store_crud.is_limited(product) and product.stock < quantity:
            raise HTTPException(status_code=400, detail="재고가 부족합니다")
        total = product.price * quantity
        point_used = payload.point_use or 0
        if point_used < 0:
            raise HTTPException(status_code=400, detail="쌀포인트 사용량이 올바르지 않습니다")
        if point_used > max_store_point_discount(total):
            raise HTTPException(status_code=400, detail=f"쌀포인트는 구매 금액의 {STORE_POINT_DISCOUNT_RATE_PERCENT}%까지만 쓸 수 있습니다")
        if point_used and point_crud.get_balance(db, user.user_id) < point_used:
            raise HTTPException(status_code=400, detail="쌀포인트가 부족합니다")
        amount = total - point_used
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
        storage_item_ids=storage_item_ids,
        point_used=point_used,
    )
    return PaymentPrepareResponse(
        payment_id=payment.payment_id,
        order_name=payment.order_name,
        amount=payment.amount,
        point_used=payment.point_used,
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
    # 환불 대기·환불 실패(수동 처리)도 사용자에게는 "취소됨"으로 보여준다
    status = "cancelled" if outcome["status"] in ("cancel_requested", "cancel_failed") else outcome["status"]
    response = PaymentCompleteResponse(
        payment_id=payment_id, order_type=payment.order_type, status=status, message=outcome["message"],
        amount=payment.amount, target_id=payment.target_id, quantity=payment.quantity,
    )

    if payment.order_type == "kuji_draw" and outcome["conflicts"]:
        kuji = kuji_crud.get_kuji_set(db, payment.target_id)
        response.kuji_draw = build_draw_response(db, kuji, [], outcome["conflicts"], False, 0)
    if status != "paid":
        return response

    if payment.order_type in ("raffle_entry", "store_funding"):
        entry = db.query(RaffleEntry).filter(RaffleEntry.payment_id == payment_id).first()
        entry.total_ticket_count = raffle_crud.get_user_total_ticket_count(db, entry.raffle_product_id, user.user_id)
        response.raffle_entry = RaffleEntryCreateResponse.model_validate(entry)
    elif payment.order_type == "kuji_draw":
        kuji, drawn, got_last_one = kuji_crud.get_paid_draw(
            db, payment.target_id, user.user_id, list(payment.ticket_numbers or []), payment_id,
        )
        response.kuji_draw = build_draw_response(db, kuji, drawn, [], got_last_one, payment.amount)
    elif payment.order_type == "shipping_fee":
        response.shipping = [
            StorageItemResponse(**item) for item in storage_crud.get_user_storage_items(db, user.user_id)
            if item["shipping_payment_id"] == payment_id
        ]
    else:
        item = db.query(StorageItem).filter(StorageItem.payment_id == payment_id).first()
        product = store_crud.get_store_product(db, payment.target_id, include_deleted=True)
        response.store_purchase = StorePurchaseResponse(
            **store_purchase_response(product, item), point_used=payment.point_used or 0,
        )
    return response
