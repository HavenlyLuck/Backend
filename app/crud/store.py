from datetime import datetime, timedelta, timezone
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from typing import Optional

from app.models.store import StoreProduct
from app.models.raffle import RaffleProduct
from app.models.free_ticket import FreeTicket
from app.models.user import User
from app.crud import storage as storage_crud
from app.crud import inventory as inventory_crud


def create_store_product(
    db: Session,
    admin_id: int,
    product_name: str,
    description: Optional[str],
    pay_type: str,
    category: str,
    price: int,
    stock: int,
    image_url: Optional[str],
    inventory_item_id: Optional[int] = None,
    funding_disabled: bool = False,
) -> StoreProduct:
    # 재고에서 고른 품목이면 판매 수량만큼 이 상품에 묶는다 (모자라면 InventoryError)
    if inventory_item_id is not None:
        inventory_crud.check_available(db, [(inventory_item_id, stock)])
    product = StoreProduct(
        admin_id=admin_id,
        product_name=product_name,
        description=description,
        pay_type=pay_type,
        category=category,
        price=price,
        stock=stock,
        image_url=image_url,
        funding_disabled=funding_disabled,
    )
    db.add(product)
    db.flush()
    if inventory_item_id is not None:
        inventory_crud.add_link(db, inventory_item_id, "store", product.store_product_id)
    db.commit()
    db.refresh(product)
    return product


# include_sold_out=False면 품절 상품은 뺀다 — 단 응모 전환 모금이 진행 중인 상품(재고를 모금에 묶어 0개)은 보여준다
def get_store_products(db: Session, pay_type: Optional[str] = None, include_sold_out: bool = True) -> list[StoreProduct]:
    query = db.query(StoreProduct).filter(StoreProduct.deleted_at.is_(None))
    if pay_type:
        query = query.filter(StoreProduct.pay_type == pay_type)
    if not include_sold_out:
        funding = (
            db.query(RaffleProduct.raffle_product_id)
            .filter(
                RaffleProduct.funding_store_product_id == StoreProduct.store_product_id,
                RaffleProduct.status == "funding",
            )
            .exists()
        )
        query = query.filter(or_(StoreProduct.stock > 0, funding))
    return query.order_by(StoreProduct.created_at.desc()).all()


# include_deleted=True: 이미 결제된 주문의 응답을 다시 만들 때처럼, 삭제된 상품도 찾아야 하는 경우
def get_store_product(db: Session, store_product_id: int, include_deleted: bool = False) -> Optional[StoreProduct]:
    query = db.query(StoreProduct).filter(StoreProduct.store_product_id == store_product_id)
    if not include_deleted:
        query = query.filter(StoreProduct.deleted_at.is_(None))
    return query.first()


# 재고 차감 시 동시 구매로 재고가 음수가 되지 않도록 행 잠금으로 조회
def get_store_product_for_update(db: Session, store_product_id: int) -> Optional[StoreProduct]:
    return (
        db.query(StoreProduct)
        .filter(StoreProduct.store_product_id == store_product_id)
        .with_for_update()
        .first()
    )


class StorePurchaseError(Exception):
    pass


# 쌀포인트 상점의 쿠폰(쌀 응모권) — 사면 보관함에 쌀 응모권이 바로 들어간다 (배송 상품이 아니다)
# 계정당 한 주(한국 시간 월요일 0시 ~ 다음 월요일 0시)에 이 장수까지만 살 수 있다
TICKET_CATEGORY = "coupon"
TICKET_WEEKLY_LIMIT = 2
_KST = timedelta(hours=9)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# 이번 주 시작 시각(한국 시간 월요일 0시)을 UTC로
def _week_start_utc(now: datetime) -> datetime:
    kst = now + _KST
    monday = (kst - timedelta(days=kst.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday - _KST


def is_ticket_product(product: StoreProduct) -> bool:
    return product.pay_type == "ssal" and product.category == TICKET_CATEGORY


# 이번 주에 상점에서 산 쌀 응모권 장수 (쓴 것 포함)
def tickets_bought_this_week(db: Session, user_id: int) -> int:
    return (
        db.query(func.count(FreeTicket.free_ticket_id))
        .filter(
            FreeTicket.user_id == user_id,
            FreeTicket.kind == "store_purchase",
            FreeTicket.created_at >= _week_start_utc(_utcnow()),
        )
        .scalar()
    ) or 0


# 쌀 응모권 구매 — 주간 한도 확인, 재고 차감, 쌀 응모권 지급 (commit은 호출한 쪽에서)
# 같은 사람이 동시에 사도 한도를 넘지 않게 회원 행을 잠그고 센다. 지급한 응모권 목록을 돌려준다
def fulfill_ticket_purchase(db: Session, store_product_id: int, user_id: int, quantity: int):
    if quantity <= 0:
        raise StorePurchaseError("구매 수량은 1개 이상이어야 합니다")
    db.query(User.user_id).filter(User.user_id == user_id).with_for_update().first()
    product = get_store_product_for_update(db, store_product_id)
    if not product or product.deleted_at is not None:
        raise StorePurchaseError("상품을 찾을 수 없습니다")
    if not is_ticket_product(product):
        raise StorePurchaseError("쌀 응모권 상품이 아닙니다")
    bought = tickets_bought_this_week(db, user_id)
    if bought + quantity > TICKET_WEEKLY_LIMIT:
        left = max(TICKET_WEEKLY_LIMIT - bought, 0)
        raise StorePurchaseError(
            f"쌀 응모권은 한 주에 {TICKET_WEEKLY_LIMIT}장까지 살 수 있어요"
            + (f" (이번 주 {left}장 더 살 수 있어요)" if left else ". 다음 주 월요일에 다시 살 수 있어요")
        )
    if product.stock < quantity:
        raise StorePurchaseError("재고가 부족합니다")

    product.stock -= quantity
    now = _utcnow()
    tickets = [FreeTicket(user_id=user_id, kind="store_purchase", created_at=now) for _ in range(quantity)]
    db.add_all(tickets)
    db.flush()
    return product, tickets


# 상점 구매 — 재고 차감과 보관함 적재 (commit은 호출한 쪽에서). 재고 부족이면 StorePurchaseError
def fulfill_store_purchase(
    db: Session, store_product_id: int, user_id: int, quantity: int, pay_type: str, payment_id: Optional[str] = None,
):
    if quantity <= 0:
        raise StorePurchaseError("구매 수량은 1개 이상이어야 합니다")
    product = get_store_product_for_update(db, store_product_id)
    if not product:
        raise StorePurchaseError("상품을 찾을 수 없습니다")
    if product.pay_type != pay_type:
        raise StorePurchaseError("결제 방식이 맞지 않는 상품입니다")
    if product.stock < quantity:
        raise StorePurchaseError("재고가 부족합니다")

    product.stock -= quantity
    item = storage_crud.add_store_purchase(
        db,
        user_id=user_id,
        store_product_id=product.store_product_id,
        quantity=quantity,
        amount_spent=product.price * quantity,
        payment_id=payment_id,
    )
    return product, item
