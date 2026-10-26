from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from app.models.address import ShippingAddress

MAX_ADDRESSES = 5


def _active(db: Session, user_id: int):
    return db.query(ShippingAddress).filter(ShippingAddress.user_id == user_id, ShippingAddress.deleted_at.is_(None))


def get_user_addresses(db: Session, user_id: int) -> list[ShippingAddress]:
    return (
        _active(db, user_id)
        .order_by(ShippingAddress.is_default.desc(), ShippingAddress.created_at.desc(), ShippingAddress.address_id.desc())
        .all()
    )


def get_user_address(db: Session, user_id: int, address_id: int) -> Optional[ShippingAddress]:
    return _active(db, user_id).filter(ShippingAddress.address_id == address_id).first()


# 첫 배송지는 자동으로 기본 배송지가 되고, 새 기본 배송지를 지정하면 기존 기본은 해제한다.
# 배송지는 MAX_ADDRESSES개까지 — 넘치면 기본이 아닌 배송지 중 오래된 것부터 숨긴다
def create_address(
    db: Session,
    user_id: int,
    label: str,
    recipient: str,
    phone: str,
    zip_code: Optional[str],
    address1: str,
    address2: Optional[str],
    is_default: bool,
) -> ShippingAddress:
    # 동시에 여러 개를 등록해도 개수 제한이 지켜지도록 내 배송지 행을 잠근다
    existing = (
        _active(db, user_id)
        .order_by(ShippingAddress.created_at.asc(), ShippingAddress.address_id.asc())
        .with_for_update()
        .all()
    )
    # 지울 배송지는 기본 해제 전에 고른다 — 새 배송지를 기본으로 등록해도 직전 기본 배송지는 남긴다
    overflow = len(existing) + 1 - MAX_ADDRESSES
    if overflow > 0:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for addr in [a for a in existing if not a.is_default][:overflow]:
            addr.deleted_at = now

    is_default = is_default or not existing
    if is_default:
        for addr in existing:
            addr.is_default = False

    address = ShippingAddress(
        user_id=user_id,
        label=label,
        recipient=recipient,
        phone=phone,
        zip_code=zip_code,
        address1=address1,
        address2=address2,
        is_default=is_default,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


def set_default_address(db: Session, user_id: int, address_id: int) -> Optional[ShippingAddress]:
    addresses = _active(db, user_id).with_for_update().all()
    target = next((a for a in addresses if a.address_id == address_id), None)
    if not target:
        db.rollback()
        return None
    for addr in addresses:
        addr.is_default = addr.address_id == address_id
    db.commit()
    db.refresh(target)
    return target


# 배송지 삭제 — 배송 신청 내역이 참조할 수 있으므로 숨기기만 한다.
# 기본 배송지를 지우면 남은 배송지 중 가장 최근 것이 기본이 된다
def delete_address(db: Session, user_id: int, address_id: int) -> bool:
    addresses = (
        _active(db, user_id)
        .order_by(ShippingAddress.created_at.desc(), ShippingAddress.address_id.desc())
        .with_for_update()
        .all()
    )
    target = next((a for a in addresses if a.address_id == address_id), None)
    if not target:
        db.rollback()
        return False
    target.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if target.is_default:
        target.is_default = False
        rest = [a for a in addresses if a.address_id != address_id]
        if rest:
            rest[0].is_default = True
    db.commit()
    return True
