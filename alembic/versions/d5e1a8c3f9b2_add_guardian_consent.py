"""만 19세 미만 가입자의 보호자(법정대리인) 동의 기록

- users.guardian_name / guardian_phone / guardian_ci — 보호자 본인인증으로 확인한 보호자 정보
- users.guardian_consented_at — 보호자 동의 시각

Revision ID: d5e1a8c3f9b2
Revises: c4d9e2f7a1b3
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e1a8c3f9b2'
down_revision: Union[str, Sequence[str], None] = 'c4d9e2f7a1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('guardian_name', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('guardian_phone', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('guardian_ci', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('guardian_consented_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'guardian_consented_at')
    op.drop_column('users', 'guardian_ci')
    op.drop_column('users', 'guardian_phone')
    op.drop_column('users', 'guardian_name')
