"""아이디·비밀번호 찾기

- users.ci: 본인인증 CI (사람마다 고유, 번호를 바꿔도 그대로). 예전 가입자는 비어 있다
- used_identity_verifications: 비밀번호 재설정에 쓴 본인인증 ID (재사용 방지)

Revision ID: b7e3c1d9a4f2
Revises: ea361831f243
Create Date: 2026-11-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e3c1d9a4f2'
down_revision: Union[str, Sequence[str], None] = 'ea361831f243'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('ci', sa.String(length=100), nullable=True))
    op.create_unique_constraint('uq_users_ci', 'users', ['ci'])
    op.create_table(
        'used_identity_verifications',
        sa.Column('identity_verification_id', sa.String(length=64), primary_key=True),
        sa.Column('purpose', sa.String(length=30), nullable=False),
        sa.Column('used_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('used_identity_verifications')
    op.drop_constraint('uq_users_ci', 'users', type_='unique')
    op.drop_column('users', 'ci')
