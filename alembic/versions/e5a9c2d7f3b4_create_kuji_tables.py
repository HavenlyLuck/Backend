"""create kuji tables

Revision ID: e5a9c2d7f3b4
Revises: d2f8b6a1c3e9
Create Date: 2026-10-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a9c2d7f3b4'
down_revision: Union[str, Sequence[str], None] = 'd2f8b6a1c3e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('kuji_sets',
    sa.Column('kuji_set_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('admin_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('image_url', sa.String(length=500), nullable=True),
    sa.Column('ticket_price', sa.Integer(), nullable=False),
    sa.Column('total_tickets', sa.Integer(), nullable=False),
    sa.Column('remaining_tickets', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('open', 'sold_out', 'closed', name='kuji_status'), server_default='open', nullable=False),
    sa.Column('last_one_name', sa.String(length=200), nullable=True),
    sa.Column('last_one_image_url', sa.String(length=500), nullable=True),
    sa.Column('last_one_cost', sa.Integer(), nullable=True),
    sa.Column('last_one_user_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['admin_id'], ['users.user_id'], ),
    sa.ForeignKeyConstraint(['last_one_user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('kuji_set_id')
    )
    op.create_table('kuji_prizes',
    sa.Column('kuji_prize_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('kuji_set_id', sa.Integer(), nullable=False),
    sa.Column('tier', sa.Enum('upper', 'lower', name='kuji_prize_tier'), nullable=False),
    sa.Column('grade', sa.String(length=5), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('image_url', sa.String(length=500), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('remaining_quantity', sa.Integer(), nullable=False),
    sa.Column('cost', sa.Integer(), server_default='0', nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['kuji_set_id'], ['kuji_sets.kuji_set_id'], ),
    sa.PrimaryKeyConstraint('kuji_prize_id')
    )
    op.create_index(op.f('ix_kuji_prizes_kuji_set_id'), 'kuji_prizes', ['kuji_set_id'], unique=False)
    op.create_table('kuji_tickets',
    sa.Column('kuji_ticket_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('kuji_set_id', sa.Integer(), nullable=False),
    sa.Column('ticket_number', sa.Integer(), nullable=False),
    sa.Column('kuji_prize_id', sa.Integer(), nullable=False),
    sa.Column('drawn_by_user_id', sa.Integer(), nullable=True),
    sa.Column('drawn_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['kuji_set_id'], ['kuji_sets.kuji_set_id'], ),
    sa.ForeignKeyConstraint(['kuji_prize_id'], ['kuji_prizes.kuji_prize_id'], ),
    sa.ForeignKeyConstraint(['drawn_by_user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('kuji_ticket_id'),
    sa.UniqueConstraint('kuji_set_id', 'ticket_number', name='uq_kuji_ticket_number')
    )
    op.create_index(op.f('ix_kuji_tickets_kuji_set_id'), 'kuji_tickets', ['kuji_set_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_kuji_tickets_kuji_set_id'), table_name='kuji_tickets')
    op.drop_table('kuji_tickets')
    op.drop_index(op.f('ix_kuji_prizes_kuji_set_id'), table_name='kuji_prizes')
    op.drop_table('kuji_prizes')
    op.drop_table('kuji_sets')
