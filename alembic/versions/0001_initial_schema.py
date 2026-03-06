"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("language_code", sa.String(10), nullable=False, server_default="ru"),
        sa.Column("balance_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("free_uses_left", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("referrer_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("seconds_limit", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("yukassa_sub_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_subscriptions_user_status", "subscriptions", ["user_id", "status"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("amount_rub", sa.Numeric(10, 2), nullable=True),
        sa.Column("seconds_added", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("yukassa_id", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_transactions_user_id", "transactions", ["user_id"])

    op.create_table(
        "transcriptions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("file_unique_id", sa.String(255), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("s3_key", sa.String(500), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("seconds_charged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_free", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_transcriptions_user_id", "transcriptions", ["user_id"])
    op.create_index("idx_transcriptions_status", "transcriptions", ["status"])
    op.create_index("idx_transcriptions_created_at", "transcriptions", ["created_at"])

    op.create_table(
        "usage_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_usage_log_user_id_created", "usage_log", ["user_id", "created_at"])

    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("referrer_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("referred_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("bonus_earned_rub", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "promo_code_uses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("promo_code_id", sa.Integer(), sa.ForeignKey("promo_codes.id"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("promo_code_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("promo_code_uses")
    op.drop_table("promo_codes")
    op.drop_table("referrals")
    op.drop_table("usage_log")
    op.drop_table("transcriptions")
    op.drop_table("transactions")
    op.drop_table("subscriptions")
    op.drop_table("users")
