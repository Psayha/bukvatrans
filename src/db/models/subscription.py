from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, BigInteger, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.db.models.user import User


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False)   # 'basic', 'pro'
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # 'active', 'cancelled', 'expired'
    seconds_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NULL = unlim, -1 = unlim in code
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    yukassa_sub_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
