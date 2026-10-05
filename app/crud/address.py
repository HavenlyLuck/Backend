from sqlalchemy.orm import Session
from typing import Optional

from app.models.address import ShippingAddress


def get_user_addresses(db: Session, user_id: int) -> list[ShippingAddress]:
    return (
        db.query(ShippingAddress)
        .filter(ShippingAddress.user_id == user_id)
        .order_by(ShippingAddress.is_default.desc(), ShippingAddress.created_at.desc())
        .all()
    )


def get_user_address(db: Session, user_id: int, address_id: int) -> Optional[ShippingAddress]:
    return (
        db.query(ShippingAddress)
        .filter(ShippingAddress.address_id == address_id, ShippingAddress.user_id == user_id)
        .first()
    )


# 첫 배송지는 자동으로 기본 배송지가 되고, 새 기본 배송지를 지정하면 기존 기본은 해제한다
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
    has_any = db.query(ShippingAddress.address_id).filter(ShippingAddress.user_id == user_id).first() is not None
    is_default = is_default or not has_any
    if is_default:
        db.query(ShippingAddress).filter(ShippingAddress.user_id == user_id).update({"is_default": False})

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
