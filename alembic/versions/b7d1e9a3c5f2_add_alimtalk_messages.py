"""카카오 알림톡(솔라피) 발송 대기열 — 응모 신청·응모 완료·응모 실패·택배 발송

Revision ID: b7d1e9a3c5f2
Revises: a4e8c2f6d1b9
Create Date: 2026-11-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d1e9a3c5f2'
down_revision: Union[str, Sequence[str], None] = 'a4e8c2f6d1b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'alimtalk_messages',
        sa.Column('message_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dedup_key', sa.String(length=120), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=10), server_default='pending', nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('solapi_message_id', sa.String(length=64), nullable=True),
        sa.Column('error', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('queued_at', sa.DateTime(), nullable=False),
        sa.Column('attempted_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('message_id'),
        sa.UniqueConstraint('dedup_key'),
    )
    op.create_index(op.f('ix_alimtalk_messages_user_id'), 'alimtalk_messages', ['user_id'], unique=False)
    op.create_index(op.f('ix_alimtalk_messages_status'), 'alimtalk_messages', ['status'], unique=False)
    op.create_index(op.f('ix_alimtalk_messages_created_at'), 'alimtalk_messages', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_alimtalk_messages_created_at'), table_name='alimtalk_messages')
    op.drop_index(op.f('ix_alimtalk_messages_status'), table_name='alimtalk_messages')
    op.drop_index(op.f('ix_alimtalk_messages_user_id'), table_name='alimtalk_messages')
    op.drop_table('alimtalk_messages')
