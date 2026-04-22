from datetime import datetime
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
    balance_seconds: Mapped[int] = mapped_column(Integer, default=0)
    free_uses_left: Mapped[int] = mapped_column(Integer, default=3)
    referrer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user", lazy="selectin"
    )
    transcriptions: Mapped[list["Transcription"]] = relationship(
        "Transcription", back_populates="user", lazy="noload"
    )

    def has_active_unlimited_subscription(self) -> bool:
        now = datetime.utcnow()
        for sub in self.subscriptions:
            if (
                sub.status == "active"
                and sub.seconds_limit == -1
                and sub.expires_at > now
            ):
                return True
        return False

    def has_active_subscription(self) -> bool:
        now = datetime.utcnow()
        for sub in self.subscriptions:
            if sub.status == "active" and sub.expires_at > now:
                return True
        return False

    def get_display_name(self) -> str:
        if self.first_name:
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return str(self.id)
