"""배송비 결제 · 배송 신청 취소

- payments.order_type에 'shipping_fee'(배송 신청 배송비) 추가
- payments.storage_item_ids — 배송비 결제로 배송 신청할 보관함 상품들
- storage_items.shipping_payment_id — 배송 신청 때 낸 배송비 결제 (배송 취소 시 이 결제를 환불한다)

Revision ID: c4d9e2f7a1b3
Revises: b7e3c1d9a4f2
Create Date: 2026-11-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d9e2f7a1b3'
down_revision: Union[str, Sequence[str], None] = 'b7e3c1d9a4f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TYPES = ('raffle_entry', 'kuji_draw', 'store_purchase', 'store_funding')
NEW_TYPES = OLD_TYPES + ('shipping_fee',)


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'payments', 'order_type',
        existing_type=sa.Enum(*OLD_TYPES, name='payment_order_type'),
        type_=sa.Enum(*NEW_TYPES, name='payment_order_type'),
        existing_nullable=False,
    )
    op.add_column('payments', sa.Column('storage_item_ids', sa.JSON(), nullable=True))

    op.add_column('storage_items', sa.Column('shipping_payment_id', sa.String(length=64), nullable=True))
    # 인덱스를 먼저 만들어 두면 외래 키가 그 인덱스를 같이 쓴다 (인덱스가 두 개 생기지 않게)
    op.create_index('ix_storage_items_shipping_payment_id', 'storage_items', ['shipping_payment_id'])
    op.create_foreign_key(
        'fk_storage_items_shipping_payment', 'storage_items', 'payments',
        ['shipping_payment_id'], ['payment_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_storage_items_shipping_payment', 'storage_items', type_='foreignkey')
    op.drop_index('ix_storage_items_shipping_payment_id', table_name='storage_items')
    op.drop_column('storage_items', 'shipping_payment_id')

    op.drop_column('payments', 'storage_item_ids')
    # 배송비 결제가 남아 있으면 enum을 줄일 수 없으므로 먼저 지워야 한다
    op.alter_column(
        'payments', 'order_type',
        existing_type=sa.Enum(*NEW_TYPES, name='payment_order_type'),
        type_=sa.Enum(*OLD_TYPES, name='payment_order_type'),
        existing_nullable=False,
    )
