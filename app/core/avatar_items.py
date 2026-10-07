from typing import Optional

# 쌀포인트 상점 "아바타" 탭에서 파는 아이템 목록.
# 픽셀 파츠가 프론트 코드(lib/avatar/parts.ts)에 그려져 있어서 DB가 아니라 여기서 관리하며,
# 프론트 lib/avatar/shopItems.ts와 id·slot·index를 반드시 맞춰야 한다. 가격은 이 값이 기준.
AVATAR_ITEMS: dict[str, dict] = {
    "flame-cutlass": {"name": "불칼", "price": 3000, "slot": "weapon", "index": 0},
    "santa-hat": {"name": "산타 모자", "price": 2000, "slot": "hat", "index": 0},
    "red-cape": {"name": "빨간 망토", "price": 2500, "slot": "cape", "index": 0},
    # 전체 스킨 — 몸 전체를 바꾸므로 무기·모자·망토와 같이 착용할 수 없다
    "nanami-skin": {"name": "나나미 스킨", "price": 5000, "slot": "costume", "index": 0},
    "warwick-skin": {"name": "워윅 스킨", "price": 5000, "slot": "costume", "index": 1},
}

# 겹쳐 끼는 아이템 칸
OVERLAY_SLOTS = ("weapon", "hat", "cape")
AVATAR_ITEM_SLOTS = OVERLAY_SLOTS + ("costume",)


def find_item_id(slot: str, index: int) -> Optional[str]:
    for item_id, item in AVATAR_ITEMS.items():
        if item["slot"] == slot and item["index"] == index:
            return item_id
    return None
