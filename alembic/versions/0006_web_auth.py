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
    # Add email column (was in ORM model but missing from DB).
    op.add_column(
        "users",
        sa.Column("email", sa.String(255), nullable=True),
    )
    # Partial unique index: enforces uniqueness only where email IS NOT NULL,
    # so multiple Telegram-only users (email=NULL) don't conflict.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email "
        "ON users(email) WHERE email IS NOT NULL"
    )

    # Password hash for email/password auth.
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(255), nullable=True),
    )

    # Email verification flag.
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Sequence for web-only user IDs. Telegram IDs are positive ints capped
    # around 8×10^9; starting at 10^13 leaves a safe gap.
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
