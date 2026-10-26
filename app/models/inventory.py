from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


# 재고 품목 — 떼 온 물건 하나 (같은 물건을 여러 번 입고하면 입고 기록만 늘어난다)
class InventoryItem(Base):
    __tablename__ = "inventory_items"
    item_id    = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(200), nullable=False)
    image_url  = Column(String(500), nullable=True)
    memo       = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# 입고 기록 — 언제 몇 개를 얼마에 사 왔는지. 평균 원가는 이 단가들의 수량 가중 평균
class InventoryReceipt(Base):
    __tablename__ = "inventory_receipts"
    receipt_id  = Column(Integer, primary_key=True, autoincrement=True)
    item_id     = Column(Integer, ForeignKey("inventory_items.item_id"), nullable=False, index=True)
    quantity    = Column(Integer, nullable=False)
    unit_cost   = Column(Integer, nullable=False)    # 1개당 매입 단가(원, 부가세 포함)
    received_at = Column(Date, nullable=False)       # 매입일
    supplier    = Column(String(100), nullable=True)
    memo        = Column(String(255), nullable=True)
    created_at  = Column(DateTime, server_default=func.now())


# 품목을 어느 상품에 올렸는지. 판매 중 · 판매 완료 수량은 저장하지 않고 상품 상태에서 계산한다
# (crud/inventory.py의 _link_usage) — 결제·추첨·취소 흐름이 재고를 따로 고칠 필요가 없다.
#   raffle        : raffle_products.raffle_product_id (1개)
#   store         : store_products.store_product_id (판매 수량만큼)
#   kuji_prize    : kuji_prizes.kuji_prize_id (그 상의 개수만큼)
#   kuji_last_one : kuji_sets.kuji_set_id (라스트원상 1개)
class InventoryLink(Base):
    __tablename__ = "inventory_links"
    __table_args__ = (UniqueConstraint("product_type", "product_id", name="uq_inventory_link_product"),)
    link_id      = Column(Integer, primary_key=True, autoincrement=True)
    item_id      = Column(Integer, ForeignKey("inventory_items.item_id"), nullable=False, index=True)
    product_type = Column(Enum("raffle", "store", "kuji_prize", "kuji_last_one", name="inventory_product_type"), nullable=False)
    product_id   = Column(Integer, nullable=False)
    created_at   = Column(DateTime, server_default=func.now())


# 부대비용 — 택배비 · 광고비처럼 물건 값이 아닌 돈
class Expense(Base):
    __tablename__ = "expenses"
    expense_id = Column(Integer, primary_key=True, autoincrement=True)
    spent_on   = Column(Date, nullable=False, index=True)
    label      = Column(String(100), nullable=False)
    amount     = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
