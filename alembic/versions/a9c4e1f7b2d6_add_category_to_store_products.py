"""add category to store_products

Revision ID: a9c4e1f7b2d6
Revises: e8b3c5d1a7f2
Create Date: 2026-10-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9c4e1f7b2d6'
down_revision: Union[str, Sequence[str], None] = 'e8b3c5d1a7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('store_products', sa.Column(
        'category',
        sa.Enum('figure', 'goods', 'card', 'coupon', 'avatar', name='store_category'),
        nullable=True,
    ))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('store_products', 'category')
