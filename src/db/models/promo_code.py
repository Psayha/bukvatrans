from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, BigInteger, String, Boolean, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)  # 'free_seconds', 'discount_percent'
    value: Mapped[int] = mapped_column(Integer, nullable=False)    # секунды или процент
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class PromoCodeUse(Base):
    __tablename__ = "promo_code_uses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promo_code_id: Mapped[int] = mapped_column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (UniqueConstraint("promo_code_id", "user_id"),)
