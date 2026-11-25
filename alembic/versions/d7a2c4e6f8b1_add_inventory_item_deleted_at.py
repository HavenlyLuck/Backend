"""상품 등록(재고 품목) 삭제

- inventory_items.deleted_at: 관리자 "상품 등록"에서 지운 시각 (행은 남기고 목록에서만 숨긴다)

Revision ID: d7a2c4e6f8b1
Revises: c3e5a7f9b1d2
Create Date: 2026-11-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a2c4e6f8b1'
down_revision: Union[str, Sequence[str], None] = 'c3e5a7f9b1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("inventory_items", sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("inventory_items", "deleted_at")
