from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class NoticeResponse(BaseModel):
    notice_id: int
    title: str
    content: str
    pinned: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NoticeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    pinned: bool = False


# 보낸 값만 바꾼다 (고정만 토글할 때는 pinned만 보낸다)
class NoticeUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    content: Optional[str] = Field(default=None, min_length=1)
    pinned: Optional[bool] = None
