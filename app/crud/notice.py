from typing import Optional
from sqlalchemy.orm import Session

from app.models.notice import Notice


# 고정글 먼저, 그 안에서 최신순
def get_notices(db: Session) -> list[Notice]:
    return (
        db.query(Notice)
        .order_by(Notice.pinned.desc(), Notice.created_at.desc(), Notice.notice_id.desc())
        .all()
    )


def get_notice(db: Session, notice_id: int) -> Optional[Notice]:
    return db.query(Notice).filter(Notice.notice_id == notice_id).first()


def create_notice(db: Session, admin_id: int, title: str, content: str, pinned: bool) -> Notice:
    notice = Notice(admin_id=admin_id, title=title, content=content, pinned=pinned)
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return notice


def update_notice(db: Session, notice: Notice, changes: dict) -> Notice:
    for key, value in changes.items():
        setattr(notice, key, value)
    db.commit()
    db.refresh(notice)
    return notice


def delete_notice(db: Session, notice: Notice) -> None:
    db.delete(notice)
    db.commit()
