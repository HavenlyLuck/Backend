"""create notices table

Revision ID: d2f8b6a1c3e9
Revises: c7e2a4f9d1b8
Create Date: 2026-10-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2f8b6a1c3e9'
down_revision: Union[str, Sequence[str], None] = 'c7e2a4f9d1b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('notices',
    sa.Column('notice_id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('admin_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('pinned', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['admin_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('notice_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('notices')
