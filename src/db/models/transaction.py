import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, BigInteger, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    # 'subscription', 'topup', 'refund', 'referral_bonus'
    amount_rub: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    seconds_added: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'pending', 'success', 'failed', 'refunded'
    yukassa_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
