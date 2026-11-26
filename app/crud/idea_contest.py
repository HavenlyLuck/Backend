"""
천운 아바타 아이디어 공모전 — 고객이 원하는 아바타 아이템 아이디어를 그림판에 그려 올리고,
한 주(한국 시간 월요일 0시 ~ 다음 월요일 0시)가 끝나면 관리자가 1·2·3등을 뽑아 쌀 응모권을 준다.
  1등 10장, 2등 7장, 3등 5장 — 보관함의 쌀 응모권(free_tickets, kind=idea_contest)으로 바로 들어간다.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.free_ticket import FreeTicket
from app.models.idea_contest import IdeaContestEntry, IdeaContestLike, IdeaContestWeek
from app.models.user import User

PRIZES: dict[int, int] = {1: 10, 2: 7, 3: 5}   # 등수 → 쌀 응모권 장수
# 아바타 분류 — 프론트 아바타 꾸미기 분류(lib/avatar/shopItems.ts의 WEAR_SLOTS)와 같은 값
CATEGORIES = ("hairItem", "top", "bottom", "hat", "shoes", "held", "back", "aura", "background")
MAX_ENTRIES_PER_WEEK = 1                       # 한 사람이 한 주에 올릴 수 있는 응모작 수
_KST = timedelta(hours=9)


class IdeaContestError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# 지금(UTC)이 속한 주의 월요일 (한국 날짜)
def current_week(now: Optional[datetime] = None) -> date:
    kst = (now or _utcnow()) + _KST
    return (kst - timedelta(days=kst.weekday())).date()


# 그 주의 시작 · 마감 시각 (UTC, 마감은 다음 월요일 0시)
def week_bounds(week_start: date) -> tuple[datetime, datetime]:
    start = datetime(week_start.year, week_start.month, week_start.day) - _KST
    return start, start + timedelta(days=7)


# 응모작 id → 좋아요 수, 그리고 viewer가 좋아요한 응모작 id
def _like_info(db: Session, entry_ids: list[int], viewer_id: Optional[int]) -> tuple[dict[int, int], set[int]]:
    if not entry_ids:
        return {}, set()
    counts = dict(
        db.query(IdeaContestLike.entry_id, func.count(IdeaContestLike.like_id))
        .filter(IdeaContestLike.entry_id.in_(entry_ids))
        .group_by(IdeaContestLike.entry_id)
    )
    liked: set[int] = set()
    if viewer_id is not None:
        liked = {
            eid for (eid,) in db.query(IdeaContestLike.entry_id)
            .filter(IdeaContestLike.entry_id.in_(entry_ids), IdeaContestLike.user_id == viewer_id)
        }
    return {k: int(v) for k, v in counts.items()}, liked


def _rows(db: Session, query, viewer_id: Optional[int] = None) -> list[dict]:
    pairs = list(query)
    counts, liked = _like_info(db, [e.entry_id for e, _ in pairs], viewer_id)
    return [
        {
            "entry_id": e.entry_id,
            "user_id": e.user_id,
            "nickname": nickname,
            "week_start": e.week_start,
            "category": e.category,
            "title": e.title,
            "description": e.description,
            "image_url": e.image_url,
            "rank": e.rank,
            "hidden": e.hidden_at is not None,
            "created_at": e.created_at,
            "like_count": counts.get(e.entry_id, 0),
            "liked": e.entry_id in liked,
        }
        for e, nickname in pairs
    ]


def _with_nickname(db: Session):
    return db.query(IdeaContestEntry, User.nickname).join(User, IdeaContestEntry.user_id == User.user_id)


# 그 주의 응모작 — 고객 화면은 가린 것·탈퇴한 사람 것을 빼고, 관리자 화면은 모두
def list_week(db: Session, week_start: date, include_hidden: bool = False, viewer_id: Optional[int] = None) -> list[dict]:
    query = _with_nickname(db).filter(IdeaContestEntry.week_start == week_start)
    if not include_hidden:
        query = query.filter(IdeaContestEntry.hidden_at.is_(None), User.deleted_at.is_(None))
    return _rows(db, query.order_by(IdeaContestEntry.created_at.desc(), IdeaContestEntry.entry_id.desc()), viewer_id)


def count_my_entries(db: Session, user_id: int, week_start: date) -> int:
    return (
        db.query(IdeaContestEntry)
        .filter(IdeaContestEntry.user_id == user_id, IdeaContestEntry.week_start == week_start)
        .count()
    )


def is_awarded(db: Session, week_start: date) -> bool:
    return db.get(IdeaContestWeek, week_start) is not None


# 응모 전에 확인 — 사진을 올리기 전에 막을 수 있는 건 먼저 막는다 (조건이 안 맞으면 업로드하지 않게)
def check_can_enter(db: Session, user_id: int) -> date:
    week = current_week()
    if count_my_entries(db, user_id, week) >= MAX_ENTRIES_PER_WEEK:
        raise IdeaContestError("이번 주에는 이미 응모했어요. 다음 주 월요일에 다시 참여해 주세요")
    return week


def create_entry(db: Session, user_id: int, category: str, title: str, description: Optional[str], image_url: str) -> dict:
    # 같은 사람이 동시에 올려도 한 주 한도를 넘지 않게 회원 행을 잠그고 다시 센다
    db.query(User.user_id).filter(User.user_id == user_id).with_for_update().first()
    week = check_can_enter(db, user_id)
    entry = IdeaContestEntry(user_id=user_id, week_start=week, category=category, title=title, description=description, image_url=image_url)
    db.add(entry)
    db.commit()
    return get_entry_dict(db, entry.entry_id, user_id)


def get_entry(db: Session, entry_id: int) -> Optional[IdeaContestEntry]:
    return db.get(IdeaContestEntry, entry_id)


def get_entry_dict(db: Session, entry_id: int, viewer_id: Optional[int] = None) -> Optional[dict]:
    rows = _rows(db, _with_nickname(db).filter(IdeaContestEntry.entry_id == entry_id), viewer_id)
    return rows[0] if rows else None


# 내 응모작 지우기 — 그 주가 끝나기 전까지만 (끝난 주는 심사 중이라 못 지운다)
def delete_my_entry(db: Session, entry: IdeaContestEntry, user_id: int) -> str:
    if entry.user_id != user_id:
        raise IdeaContestError("내가 올린 응모작만 지울 수 있어요")
    if entry.week_start != current_week():
        raise IdeaContestError("마감된 주의 응모작은 지울 수 없어요")
    image_url = entry.image_url
    db.query(IdeaContestLike).filter(IdeaContestLike.entry_id == entry.entry_id).delete()
    db.delete(entry)
    db.commit()
    return image_url


# 좋아요 / 취소 — 한 계정이 한 응모작에 한 번. 내 응모작 · 가린 응모작 · 마감된 주 응모작에는 못 누른다.
# 좋아요 수와 내가 눌렀는지를 돌려준다 (commit까지 한다)
def set_like(db: Session, entry: IdeaContestEntry, user_id: int, like: bool) -> tuple[int, bool]:
    if like:
        if entry.user_id == user_id:
            raise IdeaContestError("내 응모작에는 좋아요를 누를 수 없어요")
        if entry.hidden_at is not None:
            raise IdeaContestError("응모작을 찾을 수 없어요")
        if entry.week_start != current_week():
            raise IdeaContestError("마감된 주의 응모작에는 좋아요를 누를 수 없어요")
        exists = db.query(IdeaContestLike.like_id).filter_by(entry_id=entry.entry_id, user_id=user_id).first()
        if not exists:
            db.add(IdeaContestLike(entry_id=entry.entry_id, user_id=user_id))
            try:
                db.commit()
            except IntegrityError:   # 두 번 빠르게 눌러 동시에 들어온 경우 — 이미 눌린 것으로 본다
                db.rollback()
    else:
        db.query(IdeaContestLike).filter_by(entry_id=entry.entry_id, user_id=user_id).delete()
        db.commit()
    count = db.query(func.count(IdeaContestLike.like_id)).filter(IdeaContestLike.entry_id == entry.entry_id).scalar() or 0
    return int(count), like


def set_hidden(db: Session, entry: IdeaContestEntry, hidden: bool) -> None:
    if hidden and entry.rank is not None:
        raise IdeaContestError("이미 수상한 응모작은 가릴 수 없어요")
    entry.hidden_at = _utcnow() if hidden else None
    db.commit()


# 시상 — 끝난 주에서 1등부터 차례로 고른 응모작(1~3개)에 등수를 매기고 쌀 응모권을 넣는다. commit까지 한다
def award_week(db: Session, week_start: date, entry_ids: list[int], admin_id: int) -> None:
    if not 1 <= len(entry_ids) <= len(PRIZES):
        raise IdeaContestError(f"수상작은 1~{len(PRIZES)}개를 골라주세요")
    if len(set(entry_ids)) != len(entry_ids):
        raise IdeaContestError("같은 응모작을 두 번 고를 수 없어요")
    if week_start >= current_week():
        raise IdeaContestError("아직 진행 중인 주예요. 주가 끝난 뒤(다음 주 월요일부터) 뽑을 수 있어요")
    if is_awarded(db, week_start):
        raise IdeaContestError("이미 시상을 마친 주예요")

    entries = (
        db.query(IdeaContestEntry)
        .filter(IdeaContestEntry.entry_id.in_(entry_ids))
        .with_for_update()
        .all()
    )
    by_id = {e.entry_id: e for e in entries}
    picked = []
    for entry_id in entry_ids:
        e = by_id.get(entry_id)
        if not e or e.week_start != week_start:
            raise IdeaContestError("그 주의 응모작이 아니에요")
        if e.hidden_at is not None:
            raise IdeaContestError("가린 응모작은 뽑을 수 없어요")
        picked.append(e)
    if len({e.user_id for e in picked}) != len(picked):
        raise IdeaContestError("한 사람은 한 번만 수상할 수 있어요")

    # 주 행을 먼저 넣는다 — 두 관리자가 동시에 눌러도 기본키가 겹쳐 한 번만 지급된다
    db.add(IdeaContestWeek(week_start=week_start, awarded_by=admin_id))
    db.flush()
    now = _utcnow()
    for rank, e in enumerate(picked, start=1):
        e.rank = rank
        db.add_all(FreeTicket(user_id=e.user_id, kind="idea_contest", created_at=now) for _ in range(PRIZES[rank]))
    db.commit()


# 최근 시상한 주들의 수상작 (최근 주부터)
def recent_winners(db: Session, weeks: int = 4, viewer_id: Optional[int] = None) -> list[dict]:
    awarded = [w for (w,) in db.query(IdeaContestWeek.week_start).order_by(IdeaContestWeek.week_start.desc()).limit(weeks)]
    if not awarded:
        return []
    rows = _rows(
        db,
        _with_nickname(db)
        .filter(IdeaContestEntry.week_start.in_(awarded), IdeaContestEntry.rank.isnot(None))
        .order_by(IdeaContestEntry.rank.asc()),
        viewer_id,
    )
    return [{"week_start": w, "winners": [r for r in rows if r["week_start"] == w]} for w in awarded]


# 관리자 — 응모작이 있었던 주 목록 (최근 주부터): 응모 수 · 시상 여부
def admin_weeks(db: Session, limit: int = 12) -> list[dict]:
    counts = (
        db.query(IdeaContestEntry.week_start, func.count(IdeaContestEntry.entry_id))
        .group_by(IdeaContestEntry.week_start)
        .order_by(IdeaContestEntry.week_start.desc())
        .limit(limit)
        .all()
    )
    weeks = {w: int(n) for w, n in counts}
    weeks.setdefault(current_week(), 0)
    awarded = {w for (w,) in db.query(IdeaContestWeek.week_start).filter(IdeaContestWeek.week_start.in_(list(weeks)))}
    this_week = current_week()
    return [
        {"week_start": w, "entry_count": weeks[w], "awarded": w in awarded, "ongoing": w == this_week}
        for w in sorted(weeks, reverse=True)
    ]
