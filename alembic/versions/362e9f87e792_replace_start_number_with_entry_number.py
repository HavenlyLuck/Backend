"""replace start_number with entry_number on raffle_entries

Revision ID: 362e9f87e792
Revises: f6dc20282893
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '362e9f87e792'
down_revision: Union[str, Sequence[str], None] = 'f6dc20282893'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('raffle_entries', sa.Column('entry_number', sa.Integer(), nullable=True))

    # 상품별로 "그 유저가 처음 응모한 시각" 순서대로 0, 1, 2... 번호를 매기고,
    # 같은 유저의 나머지 응모 row에도 동일한 번호를 채워넣는다.
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT entry_id, raffle_product_id, user_id FROM raffle_entries ORDER BY raffle_product_id, created_at, entry_id"
    )).fetchall()

    assigned: dict[tuple[int, int], int] = {}   # (raffle_product_id, user_id) -> entry_number
    next_number: dict[int, int] = {}            # raffle_product_id -> 다음 부여할 번호

    for entry_id, raffle_product_id, user_id in rows:
        key = (raffle_product_id, user_id)
        if key not in assigned:
            assigned[key] = next_number.get(raffle_product_id, 0)
            next_number[raffle_product_id] = assigned[key] + 1
        conn.execute(
            sa.text("UPDATE raffle_entries SET entry_number = :n WHERE entry_id = :entry_id"),
            {"n": assigned[key], "entry_id": entry_id},
        )

    op.alter_column('raffle_entries', 'entry_number', existing_type=sa.Integer(), nullable=False)
    op.drop_column('raffle_entries', 'start_number')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('raffle_entries', sa.Column('start_number', sa.Integer(), nullable=True))
    op.drop_column('raffle_entries', 'entry_number')
