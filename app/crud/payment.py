# 카드 결제 주문 — 응모권 · 쿠지 제비 · 결제 상점 상품을 포트원 결제로 산다.
#  1) prepare: 서버가 금액을 정해 pending 주문을 만든다 (프론트는 이 payment_id·금액으로 결제창을 연다)
#  2) complete: 포트원에 결제를 직접 조회해서 PAID이고 금액이 같으면 지급한다
#     지급할 수 없으면(그 사이 매진·제비가 먼저 나감 등) 결제를 취소한다
#  3) 서버 주기 작업이 결제 후 창을 닫아버린 주문(pending)을 마저 처리하고, 취소 대기 결제를 포트원에 취소 요청한다
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.services import portone
from app.crud import raffle as raffle_crud
from app.crud import kuji as kuji_crud
from app.crud import store as store_crud

# 결제창을 띄운 지 이 시간이 지나도 결제가 안 됐으면 버려진 주문으로 본다
PENDING_EXPIRE_MINUTES = 60
# 주기 작업은 이 시간이 지난 pending 주문만 건드린다 (결제창이 아직 열려 있을 수 있으므로)
RECONCILE_AFTER_MINUTES = 3
BATCH_SIZE = 20


class PaymentError(Exception):
    pass


class FulfillError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_payment_id() -> str:
    # 포트원 paymentId는 ASCII만 — 'pay' + UUID hex (35자)
    return f"pay{uuid.uuid4().hex}"


def create_payment(
    db: Session,
    user_id: int,
    order_type: str,
    target_id: int,
    quantity: int,
    order_name: str,
    amount: int,
    ticket_numbers: Optional[list[int]] = None,
) -> Payment:
    payment = Payment(
        payment_id=new_payment_id(),
        user_id=user_id,
        order_type=order_type,
        target_id=target_id,
        quantity=quantity,
        ticket_numbers=ticket_numbers,
        order_name=order_name[:200],
        amount=amount,
        status="pending",
        # 만료 판단을 파이썬 UTC 기준으로 하므로 DB 기본값(DB 시간대) 대신 직접 넣는다
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def _lock(db: Session, payment_id: str) -> Optional[Payment]:
    return db.query(Payment).filter(Payment.payment_id == payment_id).with_for_update().first()


# 주문 종류별 지급. 지급할 수 없으면 FulfillError, 쿠지 제비가 이미 나갔으면 그 번호들을 돌려준다
def _fulfill(db: Session, payment: Payment) -> list[int]:
    try:
        if payment.order_type == "raffle_entry":
            raffle_crud.fulfill_raffle_entry(
                db, payment.target_id, payment.user_id, payment.quantity, payment.amount, payment.payment_id,
            )
        elif payment.order_type == "kuji_draw":
            _, _, conflicts, _ = kuji_crud.fulfill_kuji_draw(
                db, payment.target_id, payment.user_id, list(payment.ticket_numbers or []), payment.amount, payment.payment_id,
            )
            return conflicts
        elif payment.order_type == "store_purchase":
            product, item = store_crud.fulfill_store_purchase(
                db, payment.target_id, payment.user_id, payment.quantity, "cash", payment.payment_id,
            )
            if item.amount_spent != payment.amount:
                raise FulfillError("결제 금액이 상품 가격과 맞지 않습니다")
    except (raffle_crud.RaffleEntryError, kuji_crud.KujiDrawError, store_crud.StorePurchaseError, LookupError) as e:
        raise FulfillError(str(e))
    return []


# 포트원에 결제 취소를 요청한다. 실패하면 cancel_requested로 남겨 두고 주기 작업이 다시 시도한다
def _try_cancel(db: Session, payment_id: str) -> bool:
    payment = _lock(db, payment_id)
    if not payment or payment.status != "cancel_requested":
        db.rollback()
        return payment is not None and payment.status == "cancelled"
    try:
        portone.cancel_payment(payment.payment_id, payment.cancel_reason or "주문 취소")
    except portone.PortOneError:
        logging.exception("payment cancel failed: %s", payment_id)
        db.rollback()
        return False
    payment.status = "cancelled"
    payment.cancelled_at = _utcnow()
    db.commit()
    return True


# 다른 곳(보관함 구매 취소 등)에서 cancel_requested로 바꾼 결제를 바로 환불 요청할 때
def try_cancel_payment(db: Session, payment_id: str) -> bool:
    return _try_cancel(db, payment_id)


def _request_cancel(db: Session, payment_id: str, reason: str) -> None:
    payment = _lock(db, payment_id)
    if payment and payment.status == "pending":
        payment.status = "cancel_requested"
        payment.cancel_reason = reason
    db.commit()
    _try_cancel(db, payment_id)


# 결제 확인 후 지급. user_id를 주면 그 사람의 주문인지도 확인한다 (주기 작업은 None)
# 반환: {"status": paid|pending|failed|cancel_requested|cancelled, "message", "conflicts"}
def complete_payment(db: Session, payment_id: str, user_id: Optional[int] = None) -> dict:
    payment = _lock(db, payment_id)
    if not payment or (user_id is not None and payment.user_id != user_id):
        db.rollback()
        raise LookupError("결제 내역을 찾을 수 없습니다")
    if payment.status != "pending":
        # 이미 처리된 주문 — 결제 완료 요청이 두 번 와도 같은 결과를 돌려준다
        result = {"status": payment.status, "message": payment.cancel_reason, "conflicts": []}
        db.rollback()
        return result

    try:
        paid = portone.get_payment(payment_id)
    except portone.PortOneError:
        db.rollback()
        raise PaymentError("결제 결과를 확인하지 못했습니다. 잠시 후 다시 시도해주세요")

    if not paid or paid["status"] != "PAID":
        expired = payment.created_at and payment.created_at < _utcnow() - timedelta(minutes=PENDING_EXPIRE_MINUTES)
        if (paid and paid["status"] in ("FAILED", "CANCELLED")) or (expired and (not paid or paid["status"] == "READY")):
            payment.status = "failed"
            db.commit()
            return {"status": "failed", "message": "결제가 완료되지 않았습니다", "conflicts": []}
        # 확인한 시각을 남겨 주기 작업이 오래된 주문만 붙잡고 있지 않게 돌아가며 확인한다
        payment.updated_at = _utcnow()
        db.commit()
        return {"status": "pending", "message": "결제가 아직 완료되지 않았습니다", "conflicts": []}

    if paid["amount"] != payment.amount or paid["currency"] != "KRW":
        db.rollback()
        reason = "결제 금액이 주문 금액과 달라 결제를 취소했습니다"
        _request_cancel(db, payment_id, reason)
        return {"status": "cancelled", "message": reason, "conflicts": []}

    try:
        conflicts = _fulfill(db, payment)
        reason = "이미 다른 분이 뽑은 제비가 있어 결제를 취소했습니다" if conflicts else None
    except FulfillError as e:
        conflicts, reason = [], f"{e} — 결제를 취소했습니다"

    if reason:
        db.rollback()
        _request_cancel(db, payment_id, reason)
        return {"status": "cancelled", "message": reason, "conflicts": conflicts}

    payment.status = "paid"
    payment.paid_at = paid["paid_at"] or _utcnow()
    db.commit()
    return {"status": "paid", "message": None, "conflicts": []}


# 주기 작업 — 결제는 했는데 완료 요청이 안 온 주문(창을 닫았거나 네트워크 끊김)을 마저 처리하고,
# 취소 대기 결제(지급 실패 · 응모 취소)를 포트원에 취소 요청한다
def settle_payments(db: Session) -> None:
    cutoff = _utcnow() - timedelta(minutes=RECONCILE_AFTER_MINUTES)
    pending_ids = [
        pid for (pid,) in db.query(Payment.payment_id)
        .filter(Payment.status == "pending", Payment.created_at <= cutoff)
        .order_by(Payment.updated_at)
        .limit(BATCH_SIZE)
    ]
    cancel_ids = [
        pid for (pid,) in db.query(Payment.payment_id)
        .filter(Payment.status == "cancel_requested")
        .order_by(Payment.updated_at)
        .limit(BATCH_SIZE)
    ]
    db.rollback()

    for pid in pending_ids:
        try:
            complete_payment(db, pid)
        except Exception:
            db.rollback()
            logging.exception("payment reconcile failed: %s", pid)
    for pid in cancel_ids:
        _try_cancel(db, pid)


def get_payment(db: Session, payment_id: str) -> Optional[Payment]:
    return db.query(Payment).filter(Payment.payment_id == payment_id).first()
