"""link reviews to storage items (받은 상품에만 후기)

Revision ID: b7c3e9a1d5f4
Revises: a9d4f2c6b8e1
Create Date: 2026-11-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c3e9a1d5f4'
down_revision: Union[str, Sequence[str], None] = 'a9d4f2c6b8e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reviews', sa.Column('storage_item_id', sa.Integer(), nullable=True))
    op.add_column('reviews', sa.Column('product_name', sa.String(length=200), nullable=True))
    op.add_column('reviews', sa.Column('product_type', sa.Enum('raffle', 'store', 'kuji', name='review_product_type'), nullable=True))
    op.create_foreign_key('fk_reviews_storage_item', 'reviews', 'storage_items', ['storage_item_id'], ['storage_item_id'])
    op.create_unique_constraint('uq_reviews_storage_item', 'reviews', ['storage_item_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_reviews_storage_item', 'reviews', type_='foreignkey')
    op.drop_constraint('uq_reviews_storage_item', 'reviews', type_='unique')
    op.drop_column('reviews', 'product_type')
    op.drop_column('reviews', 'product_name')
    op.drop_column('reviews', 'storage_item_id')
