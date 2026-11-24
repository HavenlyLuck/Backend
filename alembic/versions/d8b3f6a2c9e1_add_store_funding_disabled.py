"""결제 상점 상품 응모 전환 막기

- store_products.funding_disabled: 랜덤 상품처럼 응모로 돌리면 안 되는 상품 (상세에 "응모 전환" 칸이 안 보인다)

Revision ID: d8b3f6a2c9e1
Revises: c5a9e2d7f1b4
Create Date: 2026-11-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8b3f6a2c9e1'
down_revision: Union[str, Sequence[str], None] = 'c5a9e2d7f1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('store_products', sa.Column('funding_disabled', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('store_products', 'funding_disabled')
