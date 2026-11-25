# 카카오 알림톡 — 응모·추첨·배송 처리와 같은 트랜잭션에서 보낼 알림을 쌓고(enqueue_*),
# 서버 주기 작업(app/main.py settle_loop)이 send_pending으로 솔라피에 보낸다.
# 처리가 롤백되면 알림도 같이 사라지고, 솔라피가 느리거나 멈춰도 응모·결제 요청은 기다리지 않는다.
import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.alimtalk import AlimtalkMessage
from app.models.raffle import RaffleEntry, RaffleProduct
from app.models.user import User
from app.services import alimtalk as alimtalk_service

SEND_BATCH = 20
# 솔라피는 같은 번호로 짧은 시간에 연달아 보내면 거부한다 — 한 회원에게는 이 간격을 두고 하나씩 보낸다
# (예: 응모권을 사자마자 매진되면 응모 완료 → 응모 완성 순으로 이 간격을 두고 나간다)
PER_USER_GAP = timedelta(seconds=60)
MAX_ATTEMPTS = 3
# 이보다 오래 대기한 알림은 보내지 않는다 (솔라피 설정 전에 쌓인 것이 한꺼번에 나가지 않게)
STALE_AFTER = timedelta(hours=6)
# 보내는 중(sending)에서 이만큼 멈춰 있으면 서버가 도중에 꺼진 것 — 두 번 나가지 않게 실패로 둔다
STUCK_AFTER = timedelta(minutes=10)
# 발송 기록 보관 기간
RETENTION = timedelta(days=90)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# 알림을 쌓는다 (commit은 호출한 쪽에서). 같은 dedup_key가 이미 있으면 쌓지 않는다.
# 호출하는 곳은 모두 상품·보관함 행을 잠근 뒤라 같은 알림이 동시에 쌓이지 않는다
def _enqueue(db: Session, kind: str, user_id: int, dedup_key: str, data: dict) -> None:
    exists = db.query(AlimtalkMessage.message_id).filter(AlimtalkMessage.dedup_key == dedup_key).first()
    if exists:
        return
    # DB 합계(SUM)는 MySQL에서 Decimal로 온다 — JSON 칸에 넣을 수 있게 정수로 바꾼다
    data = {k: int(v) if isinstance(v, Decimal) else v for k, v in data.items()}
    now = _utcnow()
    db.add(AlimtalkMessage(
        dedup_key=dedup_key, user_id=user_id, kind=kind, data=data,
        status="pending", attempts=0, created_at=now, queued_at=now,
    ))


KST = timezone(timedelta(hours=9))


def _won(amount: int) -> str:
    return f"{amount:,}원"


# 응모 완료(접수) — 응모 1건(결제 1건 또는 무료 응모권 사용 1번)마다. sold_after: 이번 응모까지 팔린 응모권 수
def enqueue_raffle_entered(db: Session, product: RaffleProduct, entry: RaffleEntry, sold_after: int) -> None:
    _enqueue(db, "raffle_entered", entry.user_id, f"raffle_entered:{entry.entry_id}", {
        "product_name": product.product_name,
        "ticket_count": entry.ticket_count,
        "payment": _won(entry.amount_paid) if entry.amount_paid else f"쌀 응모권 {entry.ticket_count}장 사용",
        # MySQL은 SUM 결과를 Decimal로 돌려준다 — JSON에 넣을 수 있게 int로
        "sold": int(sold_after),
        "total": int(product.total_slots),
    })


# 응모 완성 — 응모권이 매진되면 응모자 모두에게 (추첨 예정 시각과 함께). totals: [(user_id, 그 사람의 응모권 수)]
def enqueue_raffle_sold_out(db: Session, product: RaffleProduct, draw_at: Optional[datetime], totals: list[tuple[int, int]]) -> None:
    draw_text = (
        draw_at.replace(tzinfo=timezone.utc).astimezone(KST).strftime("%Y.%m.%d %H:%M") if draw_at else "매진 1분 뒤"
    )
    for user_id, tickets in totals:
        _enqueue(db, "raffle_sold_out", user_id, f"raffle_sold_out:{product.raffle_product_id}:{user_id}", {
            "product_name": product.product_name,
            "ticket_count": int(tickets),
            "total": product.total_slots,
            "draw_at": draw_text,
        })


# 응모 실패(자동 취소) — 기간 안에 매진되지 못해 자동 취소되면, 그때 남아 있던 응모자에게 환불 내역과 함께.
# _cancel_raffle 전에 부른다 (응모 기록으로 카드 결제 금액과 쌀 응모권 장수를 센다)
def enqueue_raffle_failed(db: Session, product: RaffleProduct) -> None:
    per_user: dict[int, dict[str, int]] = {}
    for user_id, tickets, paid in (
        db.query(RaffleEntry.user_id, RaffleEntry.ticket_count, RaffleEntry.amount_paid)
        .filter(RaffleEntry.raffle_product_id == product.raffle_product_id)
    ):
        u = per_user.setdefault(user_id, {"tickets": 0, "paid": 0, "free": 0})
        u["tickets"] += tickets
        if paid:
            u["paid"] += paid
        else:
            u["free"] += tickets
    for user_id, u in per_user.items():
        parts = []
        if u["paid"]:
            parts.append(f"카드 결제 {_won(u['paid'])} 취소")
        if u["free"]:
            parts.append(f"쌀 응모권 {u['free']}장 반환")
        _enqueue(db, "raffle_failed", user_id, f"raffle_failed:{product.raffle_product_id}:{user_id}", {
            "product_name": product.product_name,
            "ticket_count": u["tickets"],
            "refund": ", ".join(parts) or "없음",
        })


# 배송 출발 — 발송 처리한 박스(같은 회원·같은 송장)마다
def enqueue_shipped(db: Session, user_id: int, first_item_id: int, item_names: list[str], carrier: str, tracking_number: str) -> None:
    name = item_names[0] if item_names else "주문 상품"
    if len(item_names) > 1:
        name = f"{name} 외 {len(item_names) - 1}건"
    _enqueue(db, "shipped", user_id, f"shipped:{user_id}:{first_item_id}", {
        "product_name": name,
        "carrier": carrier,
        "tracking_number": tracking_number,
    })


def _valid_phone(phone: Optional[str]) -> Optional[str]:
    digits = re.sub(r"\D", "", phone or "")
    return digits if re.fullmatch(r"01\d{8,9}", digits) else None


def _finish(msg: AlimtalkMessage, status: str, error: Optional[str] = None) -> None:
    msg.status = status
    msg.error = error[:500] if error else None
    if status == "sent":
        msg.sent_at = _utcnow()


# 대기 중인 알림을 솔라피로 보낸다 (서버 주기 작업). 여러 서버 프로세스가 동시에 불러도
# 행 잠금 뒤 sending으로 바꿔 커밋하고 나서 보내므로 한 건은 한 번만 나간다
def send_pending(db: Session) -> None:
    now = _utcnow()

    # 솔라피 설정이 없으면 쌓인 알림은 보내지 않은 것으로 정리한다 (나중에 설정해도 지난 알림이 몰려 나가지 않게)
    if not alimtalk_service.is_configured():
        db.query(AlimtalkMessage).filter(AlimtalkMessage.status == "pending").update(
            {"status": "skipped", "error": "솔라피 설정(API 키·pfId)이 없어 보내지 않았어요"}, synchronize_session=False,
        )
        db.commit()
        return

    db.query(AlimtalkMessage).filter(
        AlimtalkMessage.status == "sending", AlimtalkMessage.attempted_at <= now - STUCK_AFTER,
    ).update({"status": "failed", "error": "보내는 도중 서버가 멈춰 결과를 확인하지 못했어요"}, synchronize_session=False)

    batch = (
        db.query(AlimtalkMessage)
        .filter(AlimtalkMessage.status == "pending")
        .order_by(AlimtalkMessage.message_id.asc())
        .limit(SEND_BATCH * 5)
        .with_for_update()
        .all()
    )
    # 최근 PER_USER_GAP 안에 알림을 보냈거나(보내는 중이거나) 보내려다 거부당한 회원은 이번에 건너뛴다
    recent = now - PER_USER_GAP
    busy_users = {
        uid for (uid,) in db.query(AlimtalkMessage.user_id).filter(
            AlimtalkMessage.user_id.in_({m.user_id for m in batch}),
            AlimtalkMessage.attempted_at > recent,
            AlimtalkMessage.status.in_(["sending", "sent", "pending"]),
        )
    } if batch else set()
    claimed = []
    for msg in batch:
        if msg.queued_at <= now - STALE_AFTER:
            _finish(msg, "skipped", "너무 오래 대기해 보내지 않았어요")
            continue
        if len(claimed) >= SEND_BATCH or msg.user_id in busy_users:
            continue
        busy_users.add(msg.user_id)   # 한 회원에게는 한 번에 하나씩
        msg.status = "sending"
        msg.attempts += 1
        msg.attempted_at = now
        claimed.append(msg.message_id)
    db.commit()

    for message_id in claimed:
        msg = db.query(AlimtalkMessage).filter(AlimtalkMessage.message_id == message_id).first()
        if msg is None or msg.status != "sending":
            continue
        _send_one(db, msg)
        db.commit()


def _send_one(db: Session, msg: AlimtalkMessage) -> None:
    template = alimtalk_service.template_id(msg.kind)
    if not template:
        _finish(msg, "skipped", f"{alimtalk_service.KIND_LABELS.get(msg.kind, msg.kind)} 템플릿 ID가 설정되지 않았어요")
        return
    user = db.query(User).filter(User.user_id == msg.user_id).first()
    if user is None or user.deleted_at is not None:
        _finish(msg, "skipped", "탈퇴한 회원이에요")
        return
    phone = _valid_phone(user.phone)
    if not phone:
        _finish(msg, "skipped", "휴대폰 번호가 없어요")
        return

    variables = alimtalk_service.build_variables(msg.kind, msg.data or {})
    try:
        msg.solapi_message_id = alimtalk_service.send(phone, template, variables)
    except alimtalk_service.AlimtalkError as e:
        if e.throttled:
            # 번호별 발송 간격 제한 — 실패 횟수로 세지 않고 PER_USER_GAP 뒤에 다시 보낸다 (STALE_AFTER가 지나면 포기)
            msg.status = "pending"
            msg.attempts -= 1
            msg.error = str(e)[:500]
            return
        if e.retryable and msg.attempts < MAX_ATTEMPTS:
            msg.status = "pending"
            msg.error = str(e)[:500]
        else:
            logging.warning("alimtalk %s failed: %s", msg.message_id, e)
            _finish(msg, "failed", str(e))
        return
    _finish(msg, "sent")


# 관리자 — 최근 발송 기록 (회원 닉네임과 함께)
def list_messages(db: Session, status: Optional[str], limit: int = 100, message_id: Optional[int] = None) -> list[dict]:
    q = (
        db.query(AlimtalkMessage, User.nickname)
        .outerjoin(User, User.user_id == AlimtalkMessage.user_id)
    )
    if status:
        q = q.filter(AlimtalkMessage.status == status)
    if message_id is not None:
        q = q.filter(AlimtalkMessage.message_id == message_id)
    rows = q.order_by(AlimtalkMessage.message_id.desc()).limit(limit).all()
    return [
        {
            "message_id": m.message_id,
            "user_id": m.user_id,
            "nickname": nickname,
            "kind": m.kind,
            "data": m.data or {},
            "status": m.status,
            "attempts": m.attempts,
            "solapi_message_id": m.solapi_message_id,
            "error": m.error,
            "created_at": m.created_at,
            "sent_at": m.sent_at,
        }
        for m, nickname in rows
    ]


def count_by_status(db: Session) -> dict[str, int]:
    rows = db.query(AlimtalkMessage.status, func.count(AlimtalkMessage.message_id)).group_by(AlimtalkMessage.status).all()
    return {status: int(n) for status, n in rows}


class AlimtalkRetryError(Exception):
    pass


# 관리자 — 실패·건너뛴 알림을 다시 보낸다 (다음 주기에 나간다)
def retry_message(db: Session, message_id: int) -> AlimtalkMessage:
    msg = db.query(AlimtalkMessage).filter(AlimtalkMessage.message_id == message_id).with_for_update().first()
    if msg is None:
        raise LookupError("알림을 찾을 수 없어요")
    if msg.status not in ("failed", "skipped"):
        raise AlimtalkRetryError("실패했거나 보내지 않은 알림만 다시 보낼 수 있어요")
    msg.status = "pending"
    msg.attempts = 0
    msg.error = None
    msg.queued_at = _utcnow()
    db.commit()
    db.refresh(msg)
    return msg


# 보관 기간이 지난 발송 기록 정리 (1시간마다)
def purge_old(db: Session) -> None:
    db.query(AlimtalkMessage).filter(AlimtalkMessage.created_at <= _utcnow() - RETENTION).delete(synchronize_session=False)
    db.commit()
