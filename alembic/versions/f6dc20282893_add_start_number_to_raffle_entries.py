"""add start_number to raffle_entries

Revision ID: f6dc20282893
Revises: c3d8a6f2e4b1
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6dc20282893'
down_revision: Union[str, Sequence[str], None] = 'c3d8a6f2e4b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('raffle_entries', sa.Column('start_number', sa.Integer(), nullable=True))

    # 기존 행은 (raffle_product_id, entry_id) 순서대로 응모권 수를 누적한 값으로 백필
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT entry_id, raffle_product_id, ticket_count FROM raffle_entries ORDER BY raffle_product_id, entry_id"
    )).fetchall()

    running_totals: dict[int, int] = {}
    for entry_id, raffle_product_id, ticket_count in rows:
        start = running_totals.get(raffle_product_id, 0)
        conn.execute(
            sa.text("UPDATE raffle_entries SET start_number = :start WHERE entry_id = :entry_id"),
            {"start": start, "entry_id": entry_id},
        )
        running_totals[raffle_product_id] = start + ticket_count

    op.alter_column('raffle_entries', 'start_number', existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('raffle_entries', 'start_number')
