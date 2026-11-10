"""찜한 상품에 응모 상품 추가

- wishlist_items: raffle_product_id 추가, store_product_id는 비어 있을 수 있게 (한 행 = 상점 상품 또는 응모 상품 하나)

Revision ID: ea361831f243
Revises: 7918e13503ac
Create Date: 2026-11-10 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea361831f243'
down_revision: Union[str, Sequence[str], None] = '7918e13503ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('wishlist_items', 'store_product_id', existing_type=sa.Integer(), nullable=True)
    op.add_column('wishlist_items', sa.Column('raffle_product_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_wishlist_items_raffle_product', 'wishlist_items', 'raffle_products',
        ['raffle_product_id'], ['raffle_product_id'],
    )
    op.create_unique_constraint('uq_wishlist_user_raffle', 'wishlist_items', ['user_id', 'raffle_product_id'])


def downgrade() -> None:
    op.execute("DELETE FROM wishlist_items WHERE store_product_id IS NULL")
    op.drop_constraint('uq_wishlist_user_raffle', 'wishlist_items', type_='unique')
    op.drop_constraint('fk_wishlist_items_raffle_product', 'wishlist_items', type_='foreignkey')
    op.drop_column('wishlist_items', 'raffle_product_id')
    op.alter_column('wishlist_items', 'store_product_id', existing_type=sa.Integer(), nullable=False)
