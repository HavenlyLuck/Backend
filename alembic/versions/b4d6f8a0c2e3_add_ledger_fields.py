"""주간 장부 · 판매 방식 · 쿠지 쌀포인트 상

- inventory_receipts.tax_free: 면세 입고 (기존 메모가 "[면세]"로 시작하면 true로 옮기고 메모에서 뗀다)
- raffle_products / store_products / kuji_prizes .catalog_item_id, kuji_sets.last_one_catalog_item_id:
  게시할 때 고른 등록 상품(inventory_items) — 재고 묶기 없이 "어떤 물건인지"만 (장부용)
- store_products.sale_mode: limited(한정, 기존 상품) / regular(일반 — 재고 확인·차감 안 함)
- kuji_prizes.point_amount: 쌀포인트 상 (하위상만, 뽑히면 바로 적립)
- free_tickets.store_product_id: 쌀포인트 상점에서 산 쿠폰 상품 (장부용)
- point_transactions.reason: kuji_prize (쿠지 쌀포인트 상 당첨)

Revision ID: b4d6f8a0c2e3
Revises: a2c4e6b8d0f1
Create Date: 2026-11-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4d6f8a0c2e3'
down_revision: Union[str, Sequence[str], None] = 'a2c4e6b8d0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_REASONS = ("store_purchase", "admin_grant", "raffle_consolation", "avatar_purchase", "withdrawal",
               "store_discount", "store_discount_refund")
NEW_REASONS = OLD_REASONS + ("kuji_prize",)

TAG = "[면세]"


def _catalog_fk(table: str, column: str) -> None:
    op.add_column(table, sa.Column(column, sa.Integer(), nullable=True))
    op.create_foreign_key(f"fk_{table}_{column}", table, "inventory_items", [column], ["item_id"])


def upgrade() -> None:
    """Upgrade schema."""
    # 면세 입고
    op.add_column("inventory_receipts", sa.Column("tax_free", sa.Boolean(), nullable=False, server_default="0"))
    # 메모가 "[면세]"로 시작하면 면세로 옮기고 메모에서 뗀다 (MySQL SUBSTRING은 글자 단위 — "[면세]"는 4글자)
    op.execute(
        f"UPDATE inventory_receipts SET tax_free = 1, memo = NULLIF(TRIM(SUBSTRING(memo, {len(TAG) + 1})), '') "
        f"WHERE memo LIKE '{TAG}%'"
    )

    # 등록 상품 연결
    _catalog_fk("raffle_products", "catalog_item_id")
    _catalog_fk("store_products", "catalog_item_id")
    _catalog_fk("kuji_prizes", "catalog_item_id")
    _catalog_fk("kuji_sets", "last_one_catalog_item_id")

    # 판매 방식 (기존 상품은 모두 한정)
    op.add_column(
        "store_products",
        sa.Column("sale_mode", sa.Enum("limited", "regular", name="store_sale_mode"), nullable=False, server_default="limited"),
    )

    # 쿠지 쌀포인트 상
    op.add_column("kuji_prizes", sa.Column("point_amount", sa.Integer(), nullable=True))
    op.alter_column(
        "point_transactions", "reason",
        existing_type=sa.Enum(*OLD_REASONS, name="point_transaction_reason"),
        type_=sa.Enum(*NEW_REASONS, name="point_transaction_reason"),
        existing_nullable=False,
    )

    # 쿠폰(쌀 응모권) 구매 상품
    op.add_column("free_tickets", sa.Column("store_product_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_free_tickets_store_product_id", "free_tickets", "store_products", ["store_product_id"], ["store_product_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_free_tickets_store_product_id", "free_tickets", type_="foreignkey")
    op.drop_column("free_tickets", "store_product_id")
    op.execute("DELETE FROM point_transactions WHERE reason = 'kuji_prize'")
    op.alter_column(
        "point_transactions", "reason",
        existing_type=sa.Enum(*NEW_REASONS, name="point_transaction_reason"),
        type_=sa.Enum(*OLD_REASONS, name="point_transaction_reason"),
        existing_nullable=False,
    )
    op.drop_column("kuji_prizes", "point_amount")
    op.drop_column("store_products", "sale_mode")
    for table, column in (("kuji_sets", "last_one_catalog_item_id"), ("kuji_prizes", "catalog_item_id"),
                          ("store_products", "catalog_item_id"), ("raffle_products", "catalog_item_id")):
        op.drop_constraint(f"fk_{table}_{column}", table, type_="foreignkey")
        op.drop_column(table, column)
    # 면세 표시는 메모 앞으로 되돌린다
    op.execute(f"UPDATE inventory_receipts SET memo = TRIM(CONCAT('{TAG} ', COALESCE(memo, ''))) WHERE tax_free = 1")
    op.drop_column("inventory_receipts", "tax_free")
