"""remove woon point, add card payments

운포인트를 없애고 응모권·쿠지·결제 상점을 포트원 카드 결제로 바꾼다.
- payments 테이블 추가, raffle_entries / storage_items에 payment_id 연결
- raffle_entries.points_spent → amount_paid, storage_items.points_spent → amount_spent
- store_products.point_type(woon/ssal) → pay_type(cash/ssal)
- point_wallets.woon_point, point_transactions.point_type 삭제 (운포인트 거래 내역도 삭제)
- users.name 추가 (본인인증 실명 — 결제창 구매자 이름)

Revision ID: a3c7e9b1d5f2
Revises: f1b6d3a8e2c7
Create Date: 2026-10-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c7e9b1d5f2'
down_revision: Union[str, Sequence[str], None] = 'f1b6d3a8e2c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_REASONS = ("raffle_entry", "store_purchase", "admin_grant", "refund", "raffle_consolation", "avatar_purchase", "kuji_draw")
NEW_REASONS = ("store_purchase", "admin_grant", "raffle_consolation", "avatar_purchase")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('name', sa.String(length=50), nullable=True))

    op.create_table(
        'payments',
        sa.Column('payment_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_type', sa.Enum('raffle_entry', 'kuji_draw', 'store_purchase', name='payment_order_type'), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('ticket_numbers', sa.JSON(), nullable=True),
        sa.Column('order_name', sa.String(length=200), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'paid', 'cancel_requested', 'cancelled', 'failed', name='payment_status'), server_default='pending', nullable=False),
        sa.Column('cancel_reason', sa.String(length=200), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('payment_id'),
    )
    op.create_index('ix_payments_user_id', 'payments', ['user_id'])
    op.create_index('ix_payments_status', 'payments', ['status'])

    # 응모 1건 = 결제 1건
    op.alter_column('raffle_entries', 'points_spent', new_column_name='amount_paid', existing_type=sa.Integer(), existing_nullable=False)
    op.add_column('raffle_entries', sa.Column('payment_id', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_raffle_entries_payment_id', 'raffle_entries', ['payment_id'])
    op.create_foreign_key('fk_raffle_entries_payment_id', 'raffle_entries', 'payments', ['payment_id'], ['payment_id'])

    op.alter_column('storage_items', 'points_spent', new_column_name='amount_spent', existing_type=sa.Integer(), existing_nullable=True)
    op.add_column('storage_items', sa.Column('payment_id', sa.String(length=64), nullable=True))
    op.create_foreign_key('fk_storage_items_payment_id', 'storage_items', 'payments', ['payment_id'], ['payment_id'])

    # 운포인트 상점 상품은 카드 결제 상품이 된다 (가격 숫자는 그대로 원으로)
    op.add_column('store_products', sa.Column('pay_type', sa.Enum('cash', 'ssal', name='store_pay_type'), nullable=True))
    op.execute("UPDATE store_products SET pay_type = IF(point_type = 'woon', 'cash', 'ssal')")
    op.alter_column('store_products', 'pay_type', existing_type=sa.Enum('cash', 'ssal', name='store_pay_type'), nullable=False)
    op.drop_column('store_products', 'point_type')

    op.drop_column('point_wallets', 'woon_point')

    # 운포인트 거래 내역은 지우고, 쌀포인트만 남으니 포인트 종류 컬럼도 없앤다
    op.execute(
        "DELETE FROM point_transactions WHERE point_type = 'woon' "
        "OR reason IN ('raffle_entry', 'refund', 'kuji_draw')"
    )
    op.drop_column('point_transactions', 'point_type')
    op.alter_column(
        "point_transactions", "reason",
        existing_type=sa.Enum(*OLD_REASONS, name="point_transaction_reason"),
        type_=sa.Enum(*NEW_REASONS, name="point_transaction_reason"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema. (지운 운포인트 잔액·거래 내역은 되살리지 않는다)"""
    op.alter_column(
        "point_transactions", "reason",
        existing_type=sa.Enum(*NEW_REASONS, name="point_transaction_reason"),
        type_=sa.Enum(*OLD_REASONS, name="point_transaction_reason"),
        existing_nullable=False,
    )
    op.add_column('point_transactions', sa.Column('point_type', sa.Enum('woon', 'ssal', name='point_transaction_type'), server_default='ssal', nullable=False))

    op.add_column('point_wallets', sa.Column('woon_point', sa.Integer(), server_default='0', nullable=False))

    op.add_column('store_products', sa.Column('point_type', sa.Enum('woon', 'ssal', name='store_point_type'), nullable=True))
    op.execute("UPDATE store_products SET point_type = IF(pay_type = 'cash', 'woon', 'ssal')")
    op.alter_column('store_products', 'point_type', existing_type=sa.Enum('woon', 'ssal', name='store_point_type'), nullable=False)
    op.drop_column('store_products', 'pay_type')

    op.drop_constraint('fk_storage_items_payment_id', 'storage_items', type_='foreignkey')
    op.drop_column('storage_items', 'payment_id')
    op.alter_column('storage_items', 'amount_spent', new_column_name='points_spent', existing_type=sa.Integer(), existing_nullable=True)

    op.drop_constraint('fk_raffle_entries_payment_id', 'raffle_entries', type_='foreignkey')
    op.drop_constraint('uq_raffle_entries_payment_id', 'raffle_entries', type_='unique')
    op.drop_column('raffle_entries', 'payment_id')
    op.alter_column('raffle_entries', 'amount_paid', new_column_name='points_spent', existing_type=sa.Integer(), existing_nullable=False)

    op.drop_index('ix_payments_status', table_name='payments')
    op.drop_index('ix_payments_user_id', table_name='payments')
    op.drop_table('payments')

    op.drop_column('users', 'name')
