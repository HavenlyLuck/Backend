# app/routers/avatar_item.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.avatar_items import AVATAR_ITEMS
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.avatar import AvatarItemResponse, AvatarItemPurchaseResponse
from app.crud import avatar_item as avatar_item_crud
from app.crud import point as point_crud

router = APIRouter()

# 아바타 아이템 목록 (가격은 서버 기준)
@router.get("", response_model=list[AvatarItemResponse])
def list_avatar_items():
    return [{"item_id": item_id, **item} for item_id, item in AVATAR_ITEMS.items()]


# 내가 보유한 아바타 아이템 id 목록
@router.get("/me", response_model=list[str])
def list_my_avatar_items(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return sorted(avatar_item_crud.get_owned_item_ids(db, user.user_id))


# 아바타 아이템 구매 — 쌀포인트 차감과 보유 등록을 한 트랜잭션으로 처리
@router.post("/{item_id}/purchase", response_model=AvatarItemPurchaseResponse)
def purchase_avatar_item(item_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = AVATAR_ITEMS.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없습니다")
    if item_id in avatar_item_crud.get_owned_item_ids(db, user.user_id):
        raise HTTPException(status_code=400, detail="이미 보유한 아이템입니다")

    try:
        owned = avatar_item_crud.add_owned_item(db, user.user_id, item_id, item["price"])
        transaction = point_crud.apply_point_change(
            db,
            user_id=user.user_id,
            point_type="ssal",
            amount=-item["price"],
            reason="avatar_purchase",
            reference_id=owned.user_avatar_item_id,
            description=f"아바타 {item['name']} 구매",
        )
    except IntegrityError:
        # 같은 아이템을 동시에 두 번 구매한 경우
        db.rollback()
        raise HTTPException(status_code=400, detail="이미 보유한 아이템입니다")
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    return {
        "item_id": item_id,
        "points_spent": item["price"],
        "remaining_ssal_point": transaction.balance_after,
    }
