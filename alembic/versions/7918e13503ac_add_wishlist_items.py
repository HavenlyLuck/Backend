"""찜한 상품

- wishlist_items: 회원별로 찜한 일반 상점 상품

Revision ID: 7918e13503ac
Revises: d4a7b2e9f1c3
Create Date: 2026-11-10 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7918e13503ac'
down_revision: Union[str, Sequence[str], None] = 'd4a7b2e9f1c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'wishlist_items',
        sa.Column('wishlist_item_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('store_product_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['store_product_id'], ['store_products.store_product_id']),
        sa.PrimaryKeyConstraint('wishlist_item_id'),
        sa.UniqueConstraint('user_id', 'store_product_id', name='uq_wishlist_user_product'),
    )
    op.create_index('ix_wishlist_items_user_id', 'wishlist_items', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_wishlist_items_user_id', table_name='wishlist_items')
    op.drop_table('wishlist_items')
