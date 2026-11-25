from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


# 응모작 — 고객 화면에는 닉네임만, 관리자 화면에는 user_id · 가림 여부도
class IdeaEntryResponse(BaseModel):
    entry_id: int
    nickname: str
    category: str   # 아바타 분류 (hat · top · held ...)
    title: str
    description: Optional[str] = None
    image_url: str
    rank: Optional[int] = None
    created_at: datetime
    mine: bool = False
    like_count: int = 0
    liked: bool = False   # 로그인한 사람이 좋아요를 눌렀는지


class IdeaLikeResponse(BaseModel):
    entry_id: int
    like_count: int
    liked: bool


class IdeaAdminEntryResponse(IdeaEntryResponse):
    user_id: int
    hidden: bool


class IdeaPrize(BaseModel):
    rank: int
    ssal_ticket: int


class IdeaWinnersWeek(BaseModel):
    week_start: date
    winners: list[IdeaEntryResponse]


# 이번 주 공모전 — starts_at · ends_at은 UTC (마감 = 다음 월요일 0시, 한국 시간)
class IdeaContestCurrentResponse(BaseModel):
    week_start: date
    starts_at: datetime
    ends_at: datetime
    prizes: list[IdeaPrize]
    max_entries_per_week: int
    my_entry_count: int = 0          # 로그인했으면 이번 주에 올린 수
    entries: list[IdeaEntryResponse]
    recent_winners: list[IdeaWinnersWeek]


class IdeaAdminWeek(BaseModel):
    week_start: date
    entry_count: int
    awarded: bool
    ongoing: bool


class IdeaAwardRequest(BaseModel):
    entry_ids: list[int]   # 1등부터 차례로 (1~3개)


class IdeaHideRequest(BaseModel):
    hidden: bool
