# 추천인 코드 · 무료 응모권(첫 구매 선물 / 추천 응모권)
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.free_ticket import FreeTicket
from app.models.raffle import RaffleEntry
from app.models.user import User

# 헷갈리는 글자(0/O, 1/I/L)를 뺀 8자리 — alembic 마이그레이션(e6a1c8d4f2b7)과 같은 규칙
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReferralError(Exception):
    pass


def new_referral_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not db.query(User.user_id).filter(User.referral_code == code).first():
            return code


# 내 추천인 코드 (예전 가입자처럼 없으면 지금 만든다)
def ensure_referral_code(db: Session, user: User) -> str:
    if not user.referral_code:
        user.referral_code = new_referral_code(db)
        db.commit()
        db.refresh(user)
    return user.referral_code


def normalize_code(code: str) -> str:
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def find_referrer(db: Session, code: str) -> Optional[User]:
    code = normalize_code(code)
    if not code:
        return None
    return db.query(User).filter(User.referral_code == code).first()


def has_bought_raffle_ticket(db: Session, user_id: int) -> bool:
    return db.query(RaffleEntry.entry_id).filter(
        RaffleEntry.user_id == user_id, RaffleEntry.payment_id.isnot(None),
    ).first() is not None


# 추천인 등록 가능 여부 — 아직 추천인이 없고, 응모권을 산 적이 없어야 한다 (첫 구매 선물이 걸려 있어서)
def can_register(db: Session, user: User) -> bool:
    return user.referred_by_user_id is None and not has_bought_raffle_ticket(db, user.user_id)


# 추천인 코드 확인 — 가입할 때(user가 아직 없음)와 마이페이지에서 등록할 때 둘 다
def resolve_referrer(db: Session, code: str, user: Optional[User] = None) -> User:
    referrer = find_referrer(db, code)
    if not referrer:
        raise ReferralError("존재하지 않는 추천인 코드예요")
    if user is not None and referrer.user_id == user.user_id:
        raise ReferralError("내 추천인 코드는 등록할 수 없어요")
    return referrer


def register_referrer(db: Session, user: User, code: str) -> User:
    # 동시에 두 번 등록되지 않게 내 행을 잠그고 다시 확인한다
    me = db.query(User).filter(User.user_id == user.user_id).with_for_update().first()
    if me.referred_by_user_id is not None:
        db.rollback()
        raise ReferralError("이미 추천인을 등록했어요")
    if has_bought_raffle_ticket(db, me.user_id):
        db.rollback()
        raise ReferralError("추천인은 첫 응모권을 사기 전에만 등록할 수 있어요")
    referrer = resolve_referrer(db, code, me)
    me.referred_by_user_id = referrer.user_id
    db.commit()
    db.refresh(me)
    return referrer


def get_referral_summary(db: Session, user: User) -> dict:
    code = ensure_referral_code(db, user)
    referred_by = None
    if user.referred_by_user_id:
        referred_by = db.query(User.nickname).filter(User.user_id == user.referred_by_user_id).scalar()
    invited = db.query(func.count(User.user_id)).filter(User.referred_by_user_id == user.user_id).scalar() or 0
    rewarded = db.query(func.count(FreeTicket.free_ticket_id)).filter(
        FreeTicket.user_id == user.user_id, FreeTicket.kind == "referral",
    ).scalar() or 0
    return {
        "referral_code": code,
        "referred_by_nickname": referred_by,
        "can_register": can_register(db, user),
        "invited_count": int(invited),
        "rewarded_count": int(rewarded),
    }


# 응모권 결제가 확인된 직후(같은 트랜잭션, commit은 호출한 쪽) — 추천인을 등록한 사람의 첫 구매면
# 본인에게 첫 구매 선물 응모권, 추천해 준 사람에게 추천 응모권을 1장씩 보관함에 넣는다. 한 사람당 한 번만.
def grant_first_purchase_reward(db: Session, user_id: int) -> None:
    user = db.query(User).filter(User.user_id == user_id).with_for_update().first()
    if not user or user.referred_by_user_id is None or user.referral_rewarded_at is not None:
        return
    user.referral_rewarded_at = _utcnow()
    db.add(FreeTicket(user_id=user.user_id, kind="first_purchase", related_user_id=user.referred_by_user_id))
    db.add(FreeTicket(user_id=user.referred_by_user_id, kind="referral", related_user_id=user.user_id))
    db.flush()


# 보관함 — 아직 쓰지 않은 무료 응모권 (오래된 것부터)
def get_unused_tickets(db: Session, user_id: int) -> list[dict]:
    rows = (
        db.query(FreeTicket, User.nickname)
        .outerjoin(User, FreeTicket.related_user_id == User.user_id)
        .filter(FreeTicket.user_id == user_id, FreeTicket.raffle_entry_id.is_(None))
        .order_by(FreeTicket.created_at.asc(), FreeTicket.free_ticket_id.asc())
        .all()
    )
    return [
        {
            "free_ticket_id": t.free_ticket_id,
            "kind": t.kind,
            "related_nickname": nickname,
            "created_at": t.created_at,
        }
        for t, nickname in rows
    ]


def lock_unused_tickets(db: Session, user_id: int, count: int) -> list[FreeTicket]:
    return (
        db.query(FreeTicket)
        .filter(FreeTicket.user_id == user_id, FreeTicket.raffle_entry_id.is_(None))
        .order_by(FreeTicket.created_at.asc(), FreeTicket.free_ticket_id.asc())
        .with_for_update()
        .limit(count)
        .all()
    )


# 응모가 취소되면 그 응모에 쓴 무료 응모권을 보관함으로 돌려준다. count가 없으면 전부. 반환: 돌려준 장수
def return_tickets(db: Session, entry_id: int, count: Optional[int] = None) -> int:
    query = (
        db.query(FreeTicket)
        .filter(FreeTicket.raffle_entry_id == entry_id)
        .order_by(FreeTicket.free_ticket_id.desc())
        .with_for_update()
    )
    tickets = query.limit(count).all() if count is not None else query.all()
    for t in tickets:
        t.raffle_entry_id = None
        t.used_at = None
    db.flush()
    return len(tickets)
