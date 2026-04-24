"""User gamification + consent + monthly reset bookkeeping.

- consent_at: timestamp of 152-ФЗ consent acceptance. NULL => user hasn't
  clicked "Agree" on first /start yet. Most flows refuse until set.
- free_uses_reset_at: the monthly Celery task sets this to the next reset
  boundary; the free_uses_left counter is topped up to 3 at that moment.
- ai_dialogs_count: gamification counter, independent of billing.
- last_seen_at: used to gate some retention / notification logic later.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("consent_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("free_uses_reset_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "ai_dialogs_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "ai_dialogs_count")
    op.drop_column("users", "free_uses_reset_at")
    op.drop_column("users", "consent_at")
