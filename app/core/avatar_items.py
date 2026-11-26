# 쌀포인트 상점 "아바타" 탭에서 파는 아이템 목록 (아바타 v3).
# 그림이 프론트 코드(lib/avatar/hd.ts)에 있어서 DB가 아니라 여기서 관리하며,
# 프론트 lib/avatar/shopItems.ts와 id·slot을 반드시 맞춰야 한다. 가격은 이 값이 기준.
AVATAR_ITEMS: dict[str, dict] = {
    "hat-red-beanie": {"name": "빨간 방울 비니", "price": 2000, "slot": "hat"},
    "hat-cap": {"name": "갈색 캡모자", "price": 2000, "slot": "hat"},
    "held-flowers": {"name": "빨간 꽃다발", "price": 2000, "slot": "held"},
    "top-cat-hoodie": {"name": "냥냥 후드티", "price": 2000, "slot": "top"},
    "hat-bunny": {"name": "토끼 귀 머리띠", "price": 2000, "slot": "hat"},
    "hat-crown": {"name": "반짝 왕관", "price": 2000, "slot": "hat"},
    "hat-cat-headphones": {"name": "냥냥 헤드폰", "price": 2000, "slot": "hat"},
    "hat-sprout": {"name": "새싹 머리핀", "price": 2000, "slot": "hat"},
    "shoes-sneakers": {"name": "흰 운동화", "price": 1500, "slot": "shoes"},
    "held-milktea": {"name": "밀크티 한 잔", "price": 2000, "slot": "held"},
    "held-balloon": {"name": "하트 풍선", "price": 2000, "slot": "held"},
    "bg-night": {"name": "달빛 밤하늘", "price": 5000, "slot": "background"},
    "bg-stage": {"name": "스포트라이트 무대", "price": 5000, "slot": "background"},
    "bg-park": {"name": "햇살 공원", "price": 5000, "slot": "background"},
    "top-neko-hoodie": {"name": "네코 후드티", "price": 2000, "slot": "top"},
    "top-aurora-jumper": {"name": "별하늘 오로라 점퍼", "price": 2000, "slot": "top"},
    "top-dracula-cape": {"name": "드라큘라 케이프", "price": 2000, "slot": "top"},
    "top-dino-hoodie": {"name": "공룡 후드티", "price": 2000, "slot": "top"},
    "top-wizard-robe": {"name": "마법사 로브", "price": 2000, "slot": "top"},
    "top-blouse": {"name": "베이직 블라우스", "price": 2000, "slot": "top"},
    "top-school-vest": {"name": "스쿨 니트 조끼", "price": 2000, "slot": "top"},
    "top-plain-hoodie": {"name": "무지 후드티", "price": 2000, "slot": "top"},
    "top-knit-sweater": {"name": "니트 스웨터", "price": 2000, "slot": "top"},
    "top-highneck": {"name": "하이넥 티셔츠", "price": 2000, "slot": "top"},
    "bottom-track-shorts": {"name": "트레이닝 반바지", "price": 2000, "slot": "bottom"},
    "bottom-cargo-pants": {"name": "카고 팬츠", "price": 2000, "slot": "bottom"},
    # 머리카락·얼굴을 통째로 바꾸는 머리
    "hair-cone-head": {"name": "뾰족 원뿔 머리", "price": 3000, "slot": "hairItem"},
    "hair-monster": {"name": "초록 괴물 머리", "price": 3000, "slot": "hairItem"},
    "hair-alien": {"name": "외계인 머리", "price": 3000, "slot": "hairItem"},
    # 오라 — 캐릭터 둘레에서 움직이는 빛 (그림은 프론트 lib/avatar/auras.ts)
    "aura-gold-halo": {"name": "금빛 후광", "price": 8000, "slot": "aura"},
    "aura-thunder": {"name": "정전기", "price": 8000, "slot": "aura"},
    "aura-blue-flame": {"name": "푸른 도깨비불", "price": 8000, "slot": "aura"},
    "aura-sakura": {"name": "벚꽃 바람", "price": 8000, "slot": "aura"},
    # 등 — 날개·망토처럼 등에 다는 장식 (그림은 프론트 lib/avatar/backs.ts). 오라와 같이 입을 수 있다
    "back-angel-wings": {"name": "천사 날개", "price": 5000, "slot": "back"},
}

# 착용 칸 — 칸마다 아이템 하나씩 (머리 모양은 무료라 상점 아이템이 아니다). 프론트 shopItems.ts의 WEAR_SLOTS와 같다
# 머리(상점 머리 — 입으면 무료 머리 모양 대신 그린다)·상의·하의·모자·신발·소품(held)·등·오라·배경
# 표정·문신 칸과 그 아이템, 댄디 가르마·짧은 스포츠머리는 없앴다 (2026-11). 오픈 전 상품 정리로 머리 6개·가죽 재킷 세트·하의 9개·별 요술봉·노을 강가·천운 행운방도 없앴다. 이미 산 회원의 보유 기록(user_avatar_items)은 남지만 착용·구매는 안 된다
AVATAR_ITEM_SLOTS = ("hairItem", "top", "bottom", "hat", "shoes", "held", "back", "aura", "background")

