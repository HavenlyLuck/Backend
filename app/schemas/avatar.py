from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

# 픽셀 캐릭터 설정. 각 값은 프론트 lib/avatar/parts.ts의 파츠/팔레트 인덱스이며,
# 개수(lt=)는 프론트의 AVATAR_LIMITS와 반드시 맞춰야 한다.
# 머리·하의는 성별마다 종류가 다르지만 개수는 같아서 범위 검사는 하나로 충분하다.
class AvatarConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v: Literal[2] = 2
    gender: Literal["m", "f"]
    skin: int = Field(ge=0, lt=4)
    hair: int = Field(ge=0, lt=4)
    hairColor: int = Field(ge=0, lt=8)
    top: int = Field(ge=0, lt=4)
    topColor: int = Field(ge=0, lt=9)
    bottom: int = Field(ge=0, lt=3)
    bottomColor: int = Field(ge=0, lt=6)
    # 착용 아이템 — 보유한 아이템만 착용할 수 있다 (routers/user.py에서 확인)
    cape: Optional[int] = Field(default=None, ge=0)
    hat: Optional[int] = Field(default=None, ge=0)
    weapon: Optional[int] = Field(default=None, ge=0)
    # 전체 스킨 — 무기·모자·망토와 같이 착용할 수 없다 (routers/user.py에서 확인)
    costume: Optional[int] = Field(default=None, ge=0)


class AvatarItemResponse(BaseModel):
    item_id: str
    name: str
    price: int   # 쌀포인트
    slot: Literal["weapon", "hat", "cape", "costume"]
    index: int


class AvatarItemPurchaseResponse(BaseModel):
    item_id: str
    points_spent: int
    remaining_ssal_point: int
