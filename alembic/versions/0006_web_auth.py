"""Web auth: email unique index, password_hash, email_verified, web user sequence.

The `email` column already exists in the ORM model but was never migrated.
This revision adds the unique index, password_hash, email_verified flag, and
a dedicated BIGINT sequence for web-only users who register without Telegram.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use IF NOT EXISTS for all DDL so the migration is safe to re-run against
    # a DB where some columns were already added by an earlier partial run.
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email "
        "ON users(email) WHERE email IS NOT NULL"
    )
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)")
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "email_verified BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "CREATE SEQUENCE IF NOT EXISTS web_user_id_seq "
        "START WITH 10000000000000 INCREMENT BY 1"
    )


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS web_user_id_seq")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "password_hash")
    op.execute("DROP INDEX IF EXISTS idx_users_email")
    op.drop_column("users", "email")
