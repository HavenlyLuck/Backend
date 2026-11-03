"""상점 → 응모 전환 모금

- raffle_products.status에 'funding'(전환 모금 중) 추가
- raffle_products.funding_store_product_id (어느 상점 상품에서 전환됐는지), converted_at (전환 시각)
- payments.order_type에 'store_funding'(전환 모금 응모권 결제) 추가

Revision ID: b3f8c2d6e4a9
Revises: a7d3e9b1c5f4
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f8c2d6e4a9'
down_revision: Union[str, Sequence[str], None] = 'a7d3e9b1c5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'raffle_products', 'status',
        existing_type=sa.Enum('open', 'completed', 'cancelled', name='raffle_status'),
        type_=sa.Enum('funding', 'open', 'completed', 'cancelled', name='raffle_status'),
        existing_nullable=False,
        existing_server_default='open',
    )
    op.add_column('raffle_products', sa.Column('funding_store_product_id', sa.Integer(), nullable=True))
    op.add_column('raffle_products', sa.Column('converted_at', sa.DateTime(), nullable=True))
    # 인덱스를 먼저 만들어 두면 외래 키가 그 인덱스를 같이 쓴다 (인덱스가 두 개 생기지 않게)
    op.create_index('ix_raffle_products_funding_store_product_id', 'raffle_products', ['funding_store_product_id'])
    op.create_foreign_key(
        'fk_raffle_products_funding_store_product', 'raffle_products', 'store_products',
        ['funding_store_product_id'], ['store_product_id'],
    )

    op.alter_column(
        'payments', 'order_type',
        existing_type=sa.Enum('raffle_entry', 'kuji_draw', 'store_purchase', name='payment_order_type'),
        type_=sa.Enum('raffle_entry', 'kuji_draw', 'store_purchase', 'store_funding', name='payment_order_type'),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'payments', 'order_type',
        existing_type=sa.Enum('raffle_entry', 'kuji_draw', 'store_purchase', 'store_funding', name='payment_order_type'),
        type_=sa.Enum('raffle_entry', 'kuji_draw', 'store_purchase', name='payment_order_type'),
        existing_nullable=False,
    )
    op.drop_constraint('fk_raffle_products_funding_store_product', 'raffle_products', type_='foreignkey')
    op.drop_index('ix_raffle_products_funding_store_product_id', table_name='raffle_products')
    op.drop_column('raffle_products', 'converted_at')
    op.drop_column('raffle_products', 'funding_store_product_id')
    op.alter_column(
        'raffle_products', 'status',
        existing_type=sa.Enum('funding', 'open', 'completed', 'cancelled', name='raffle_status'),
        type_=sa.Enum('open', 'completed', 'cancelled', name='raffle_status'),
        existing_nullable=False,
        existing_server_default='open',
    )
