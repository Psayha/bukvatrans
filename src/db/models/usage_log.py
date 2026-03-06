from datetime import datetime
from typing import Optional, Any
from sqlalchemy import Integer, BigInteger, String, ForeignKey, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class UsageLog(Base):
    __tablename__ = "usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'transcribe_start', 'transcribe_done', 'summary_request', 'payment', etc.
    meta: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
