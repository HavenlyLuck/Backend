"""add shipping tracking to storage_items

관리자가 발송 처리할 때 택배사 · 송장번호 · 발송 시각을 남긴다

Revision ID: d6f1b3c8e2a4
Revises: b8d2f4a6c1e3
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6f1b3c8e2a4'
down_revision: Union[str, Sequence[str], None] = 'b8d2f4a6c1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('storage_items', sa.Column('carrier', sa.String(length=30), nullable=True))
    op.add_column('storage_items', sa.Column('tracking_number', sa.String(length=50), nullable=True))
    op.add_column('storage_items', sa.Column('shipped_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('storage_items', 'shipped_at')
    op.drop_column('storage_items', 'tracking_number')
    op.drop_column('storage_items', 'carrier')
