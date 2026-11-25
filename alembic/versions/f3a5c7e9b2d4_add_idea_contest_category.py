"""아바타 아이디어 공모전 응모작에 아바타 분류 추가

- idea_contest_entries.category: 어느 아바타 분류의 아이템인지 (hat · top · held ... 아바타 꾸미기 분류와 같은 값)
  이미 있던 응모작은 'hat'(모자)으로 채운다

Revision ID: f3a5c7e9b2d4
Revises: e9c1b3d5f7a2
Create Date: 2026-11-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a5c7e9b2d4'
down_revision: Union[str, Sequence[str], None] = 'e9c1b3d5f7a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "idea_contest_entries",
        sa.Column("category", sa.String(length=20), nullable=False, server_default="hat"),
    )
    # 기존 행을 채운 뒤에는 기본값을 없앤다 — 새 응모작은 서버가 항상 분류를 넣는다
    op.alter_column(
        "idea_contest_entries", "category",
        existing_type=sa.String(length=20),
        existing_nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("idea_contest_entries", "category")
