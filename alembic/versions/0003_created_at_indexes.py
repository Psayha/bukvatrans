"""Indexes on created_at columns for /admin_stats aggregates.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # /admin_stats and the daily report scan last-24h / last-7d windows
    # across these tables. Without an index the planner falls back to
    # seq scan, which gets painful once the tables exceed ~100k rows.
    op.create_index("idx_users_created_at", "users", ["created_at"])
    op.create_index("idx_transactions_created_at", "transactions", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_transactions_created_at", table_name="transactions")
    op.drop_index("idx_users_created_at", table_name="users")
