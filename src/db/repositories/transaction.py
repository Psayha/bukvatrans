import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.transaction import Transaction


async def create_transaction(
    user_id: int,
    type_: str,
    status: str,
    session: AsyncSession,
    amount_rub: Optional[float] = None,
    seconds_added: Optional[int] = None,
    yukassa_id: Optional[str] = None,
    description: Optional[str] = None,
) -> Transaction:
    t = Transaction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        type=type_,
        status=status,
        amount_rub=amount_rub,
        seconds_added=seconds_added,
        yukassa_id=yukassa_id,
        description=description,
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


async def get_transaction_by_yukassa_id(
    yukassa_id: str, session: AsyncSession
) -> Optional[Transaction]:
    result = await session.execute(
        select(Transaction).where(Transaction.yukassa_id == yukassa_id)
    )
    return result.scalar_one_or_none()


async def get_user_transactions(
    user_id: int, session: AsyncSession, limit: int = 10
) -> list[Transaction]:
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.status == "success")
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
