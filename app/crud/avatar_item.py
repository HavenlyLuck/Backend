from sqlalchemy.orm import Session

from app.models.avatar_item import UserAvatarItem


def get_owned_item_ids(db: Session, user_id: int) -> set[str]:
    rows = db.query(UserAvatarItem.item_id).filter(UserAvatarItem.user_id == user_id).all()
    return {row.item_id for row in rows}


def add_owned_item(db: Session, user_id: int, item_id: str, price: int) -> UserAvatarItem:
    owned = UserAvatarItem(user_id=user_id, item_id=item_id, price=price)
    db.add(owned)
    db.flush()
    return owned
