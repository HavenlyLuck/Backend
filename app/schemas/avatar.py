from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict

# 픽셀 캐릭터 설정 (아바타 v3) — 프론트 lib/avatar/compose.ts의 AvatarConfig와 같다.
# 머리 모양 + 칸마다 착용한 상점 아이템 id. 예전 v2 설정은 프론트가 읽을 때 v3로 바꿔 그린다.
class AvatarConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v: Literal[3] = 3
    hair: Literal["buns", "short"]   # 프론트 shopItems.ts의 HAIRS (무료)
    # 칸마다 착용한 아이템 — 그 칸의 아이템이고, 보유한 것만 착용할 수 있다 (routers/user.py에서 확인)
    hairItem: Optional[str] = None    # 상점 머리 (입으면 무료 머리 모양 대신 그린다)
    face: Optional[str] = None        # 표정
    tattoo: Optional[str] = None      # 문신
    top: Optional[str] = None         # 상의
    bottom: Optional[str] = None      # 하의
    hat: Optional[str] = None         # 모자
    shoes: Optional[str] = None       # 신발
    held: Optional[str] = None        # 손
    background: Optional[str] = None  # 배경


class AvatarItemResponse(BaseModel):
    item_id: str
    name: str
    price: int   # 쌀포인트
    slot: Literal["hairItem", "face", "tattoo", "top", "bottom", "hat", "shoes", "held", "background"]


class AvatarItemPurchaseResponse(BaseModel):
    item_id: str
    points_spent: int
    remaining_ssal_point: int
