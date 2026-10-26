"""create inventory and expenses tables

재고 품목 · 입고 기록 · 품목-상품 연결, 부대비용

Revision ID: e3a7c5b9d1f6
Revises: d6f1b3c8e2a4
Create Date: 2026-10-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3a7c5b9d1f6'
down_revision: Union[str, Sequence[str], None] = 'd6f1b3c8e2a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'inventory_items',
        sa.Column('item_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('memo', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        'inventory_receipts',
        sa.Column('receipt_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('item_id', sa.Integer(), sa.ForeignKey('inventory_items.item_id'), nullable=False, index=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_cost', sa.Integer(), nullable=False),
        sa.Column('received_at', sa.Date(), nullable=False),
        sa.Column('supplier', sa.String(length=100), nullable=True),
        sa.Column('memo', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        'inventory_links',
        sa.Column('link_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('item_id', sa.Integer(), sa.ForeignKey('inventory_items.item_id'), nullable=False, index=True),
        sa.Column('product_type', sa.Enum('raffle', 'store', 'kuji_prize', 'kuji_last_one', name='inventory_product_type'), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('product_type', 'product_id', name='uq_inventory_link_product'),
    )
    op.create_table(
        'expenses',
        sa.Column('expense_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('spent_on', sa.Date(), nullable=False, index=True),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('expenses')
    op.drop_table('inventory_links')
    op.drop_table('inventory_receipts')
    op.drop_table('inventory_items')
