"""add storage_items.delivered_at (배송 조회로 배송완료가 확인된 시각)

Revision ID: d2f7b3c9e5a1
Revises: c4e8a2f6b1d3
Create Date: 2026-11-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2f7b3c9e5a1'
down_revision: Union[str, Sequence[str], None] = 'c4e8a2f6b1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('storage_items', sa.Column('delivered_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('storage_items', 'delivered_at')
