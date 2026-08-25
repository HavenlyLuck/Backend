from sqlalchemy.orm import Session
from typing import Optional, Literal

from app.models.point import PointWallet, PointTransaction


def get_or_create_wallet(db: Session, user_id: int) -> PointWallet:
    wallet = db.query(PointWallet).filter(PointWallet.user_id == user_id).with_for_update().first()
    if not wallet:
        wallet = PointWallet(user_id=user_id, woon_point=0, ssal_point=0)
        db.add(wallet)
        db.flush()
    return wallet


# 포인트 잔액을 증감시키고 거래 내역을 함께 남긴다. 잔액 부족 시 ValueError.
def apply_point_change(
    db: Session,
    user_id: int,
    point_type: Literal["woon", "ssal"],
    amount: int,
    reason: str,
    reference_id: Optional[int] = None,
    description: Optional[str] = None,
) -> PointTransaction:
    wallet = get_or_create_wallet(db, user_id)
    current = wallet.woon_point if point_type == "woon" else wallet.ssal_point
    new_balance = current + amount
    if new_balance < 0:
        raise ValueError("포인트가 부족합니다")

    if point_type == "woon":
        wallet.woon_point = new_balance
    else:
        wallet.ssal_point = new_balance

    transaction = PointTransaction(
        user_id=user_id,
        point_type=point_type,
        amount=amount,
        balance_after=new_balance,
        reason=reason,
        reference_id=reference_id,
        description=description,
    )
    db.add(transaction)
    db.flush()
    return transaction


def get_point_transactions(
    db: Session, user_id: int, point_type: Optional[str] = None
) -> list[PointTransaction]:
    query = db.query(PointTransaction).filter(PointTransaction.user_id == user_id)
    if point_type:
        query = query.filter(PointTransaction.point_type == point_type)
    return query.order_by(PointTransaction.created_at.desc()).all()
