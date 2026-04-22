"""Add indexes and tighten transactions unique constraint.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cache lookup by file_unique_id — critical for 24h de-duplication.
    op.create_index(
        "idx_transcriptions_file_unique_id",
        "transcriptions",
        ["file_unique_id"],
    )

    # Observability: find a job by its Celery task id.
    op.create_index(
        "idx_transcriptions_celery_task_id",
        "transcriptions",
        ["celery_task_id"],
    )

    # Speeds up the payment webhook idempotency check and guarantees that
    # two concurrent webhooks cannot insert duplicate payments. Partial
    # predicate excludes NULL yukassa_id rows (referral_bonus transactions
    # legitimately have no yukassa_id) and keeps semantics consistent
    # across PostgreSQL, SQLite and MySQL where NULL uniqueness differs.
    op.create_index(
        "uq_transactions_yukassa_id",
        "transactions",
        ["yukassa_id"],
        unique=True,
        postgresql_where=sa.text("yukassa_id IS NOT NULL"),
        sqlite_where=sa.text("yukassa_id IS NOT NULL"),
    )

    # Referrer lookup for real-time counters in /referral.
    op.create_index(
        "idx_users_referrer_id",
        "users",
        ["referrer_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_users_referrer_id", table_name="users")
    op.drop_index("uq_transactions_yukassa_id", table_name="transactions")
    op.drop_index("idx_transcriptions_celery_task_id", table_name="transcriptions")
    op.drop_index("idx_transcriptions_file_unique_id", table_name="transcriptions")
