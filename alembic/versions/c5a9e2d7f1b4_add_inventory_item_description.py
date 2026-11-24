"""재고 품목 설명 (상품 설명 · 상품정보제공고시)

- inventory_items.description: 상품 등록 때 "재고에서 고르기"로 상품 설명란에 그대로 복사된다

Revision ID: c5a9e2d7f1b4
Revises: b2f6d9e4a7c3
Create Date: 2026-11-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5a9e2d7f1b4'
down_revision: Union[str, Sequence[str], None] = 'b2f6d9e4a7c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('inventory_items', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('inventory_items', 'description')
