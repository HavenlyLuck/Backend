from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AlimtalkMessageResponse(BaseModel):
    message_id: int
    user_id: int
    nickname: Optional[str] = None
    kind: str
    data: dict[str, Any]
    status: str
    attempts: int
    solapi_message_id: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None


class AlimtalkTemplateStatus(BaseModel):
    kind: str
    label: str
    configured: bool


class AlimtalkOverviewResponse(BaseModel):
    configured: bool                       # 솔라피 API 키·시크릿·pfId가 모두 있는지
    templates: list[AlimtalkTemplateStatus]
    counts: dict[str, int]                 # 상태별 건수
    messages: list[AlimtalkMessageResponse]
