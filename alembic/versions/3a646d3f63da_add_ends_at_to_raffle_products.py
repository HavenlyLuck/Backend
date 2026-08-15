"""add ends_at to raffle_products

Revision ID: 3a646d3f63da
Revises: 042e5646edd5
Create Date: 2026-08-15 19:09:52.488388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a646d3f63da'
down_revision: Union[str, Sequence[str], None] = '042e5646edd5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('raffle_products', sa.Column('ends_at', sa.DateTime(), nullable=True))
    # 기존 행은 starts_at + 24시간으로 백필
    op.execute("UPDATE raffle_products SET ends_at = starts_at + INTERVAL 24 HOUR WHERE ends_at IS NULL")
    op.alter_column('raffle_products', 'ends_at', existing_type=sa.DateTime(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('raffle_products', 'ends_at')
