from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import BigInteger, String, Integer, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.db.models.subscription import Subscription
    from src.db.models.transcription import Transcription


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user_id
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), default="ru")
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    balance_seconds: Mapped[int] = mapped_column(Integer, default=0)
    free_uses_left: Mapped[int] = mapped_column(Integer, default=3)
    referrer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    free_uses_reset_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    ai_dialogs_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user", lazy="selectin"
    )
    transcriptions: Mapped[list["Transcription"]] = relationship(
        "Transcription", back_populates="user", lazy="noload"
    )

    def has_active_unlimited_subscription(self) -> bool:
        # Prod Postgres stores expires_at as TIMESTAMPTZ (tz-aware);
        # the in-memory sqlite test DB strips tzinfo. Treat a naive
        # value as UTC so the comparison works in both environments.
        now = datetime.now(timezone.utc)
        for sub in self.subscriptions:
            expires = sub.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if (
                sub.status == "active"
                and sub.seconds_limit == -1
                and expires > now
            ):
                return True
        return False

    def has_active_subscription(self) -> bool:
        now = datetime.now(timezone.utc)
        for sub in self.subscriptions:
            expires = sub.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if sub.status == "active" and expires > now:
                return True
        return False

    def get_display_name(self) -> str:
        if self.first_name:
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return str(self.id)
