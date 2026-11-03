"""add referral codes and free tickets (추천인 코드 · 첫 구매 선물/추천 응모권)

Revision ID: e6a1c8d4f2b7
Revises: d2f7b3c9e5a1
Create Date: 2026-11-03 00:00:00.000000

"""
import secrets
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6a1c8d4f2b7'
down_revision: Union[str, Sequence[str], None] = 'd2f7b3c9e5a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# app/crud/referral.py의 CODE_ALPHABET과 같다 (헷갈리는 0/O, 1/I/L 제외)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('referral_code', sa.String(length=12), nullable=True))
    op.add_column('users', sa.Column('referred_by_user_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('referral_rewarded_at', sa.DateTime(), nullable=True))
    op.create_foreign_key('fk_users_referred_by', 'users', 'users', ['referred_by_user_id'], ['user_id'])

    # 기존 회원에게도 고유 코드를 하나씩 만들어 준다
    conn = op.get_bind()
    used = set()
    for (user_id,) in conn.execute(sa.text("SELECT user_id FROM users")).fetchall():
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        while code in used:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        used.add(code)
        conn.execute(sa.text("UPDATE users SET referral_code = :c WHERE user_id = :u"), {"c": code, "u": user_id})
    op.create_unique_constraint('uq_users_referral_code', 'users', ['referral_code'])

    op.create_table(
        'free_tickets',
        sa.Column('free_ticket_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('kind', sa.Enum('first_purchase', 'referral', name='free_ticket_kind'), nullable=False),
        sa.Column('related_user_id', sa.Integer(), sa.ForeignKey('users.user_id'), nullable=True),
        sa.Column('raffle_entry_id', sa.Integer(), sa.ForeignKey('raffle_entries.entry_id'), nullable=True),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_free_tickets_user_id', 'free_tickets', ['user_id'])
    op.create_index('ix_free_tickets_raffle_entry_id', 'free_tickets', ['raffle_entry_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_free_tickets_raffle_entry_id', table_name='free_tickets')
    op.drop_index('ix_free_tickets_user_id', table_name='free_tickets')
    op.drop_table('free_tickets')
    op.drop_constraint('uq_users_referral_code', 'users', type_='unique')
    op.drop_constraint('fk_users_referred_by', 'users', type_='foreignkey')
    op.drop_column('users', 'referral_rewarded_at')
    op.drop_column('users', 'referred_by_user_id')
    op.drop_column('users', 'referral_code')
