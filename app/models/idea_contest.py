from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# 천운 아바타 아이디어 공모전 응모작 — 고객이 "이런 아바타 아이템이 있으면 좋겠다"를 그림판에 그려 올린다 (한 주에 1개).
# 한 주(한국 시간 월요일 0시 ~ 다음 월요일 0시) 단위로 모으고, 주가 끝나면 관리자가 1·2·3등을 뽑는다.
#   week_start: 그 주 월요일 (한국 날짜)
#   category  : 어느 아바타 분류의 아이템인지 — 아바타 꾸미기 분류(WearSlot)와 같은 값 (hat · top · held ...)
#   rank      : 뽑히면 1·2·3 (안 뽑히면 비어 있음)
#   hidden_at : 관리자가 부적절한 사진을 가린 시각 — 목록에서 빠진다
class IdeaContestEntry(Base):
    __tablename__ = "idea_contest_entries"
    entry_id    = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    week_start  = Column(Date, nullable=False, index=True)
    category    = Column(String(20), nullable=False)
    title       = Column(String(40), nullable=False)
    description = Column(String(300), nullable=True)
    image_url   = Column(String(500), nullable=False)
    rank        = Column(Integer, nullable=True)
    hidden_at   = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, nullable=False, default=_utcnow)


# 응모작 좋아요 — 한 계정이 한 응모작에 한 번 (다시 누르면 취소)
class IdeaContestLike(Base):
    __tablename__ = "idea_contest_likes"
    __table_args__ = (UniqueConstraint("entry_id", "user_id", name="uq_idea_contest_like"),)
    like_id    = Column(Integer, primary_key=True, autoincrement=True)
    entry_id   = Column(Integer, ForeignKey("idea_contest_entries.entry_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id    = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


# 시상을 마친 주 — 같은 주를 두 번 시상(응모권 두 번 지급)하지 않게 주마다 한 줄
class IdeaContestWeek(Base):
    __tablename__ = "idea_contest_weeks"
    week_start = Column(Date, primary_key=True)
    awarded_at = Column(DateTime, nullable=False, default=_utcnow)
    awarded_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
