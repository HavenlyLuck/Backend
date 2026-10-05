"""add sold_out_at to raffle_products

Revision ID: e8b3c5d1a7f2
Revises: d4e7b2a9c1f5
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b3c5d1a7f2'
down_revision: Union[str, Sequence[str], None] = 'd4e7b2a9c1f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('raffle_products', sa.Column('sold_out_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('raffle_products', 'sold_out_at')
