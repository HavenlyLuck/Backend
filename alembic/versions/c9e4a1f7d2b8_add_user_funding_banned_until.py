"""add users.funding_banned_until (전환 응모권 구매 제한 기한)

응모 상품으로 전환된 뒤 모금 때 산 응모권을 취소한 사람은 3일 동안 상점 전환 응모권을 살 수 없다.

Revision ID: c9e4a1f7d2b8
Revises: b3f8c2d6e4a9
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e4a1f7d2b8'
down_revision: Union[str, Sequence[str], None] = 'b3f8c2d6e4a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('funding_banned_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'funding_banned_until')
