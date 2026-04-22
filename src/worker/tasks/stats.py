import asyncio
from datetime import datetime, timedelta

from celery.utils.log import get_task_logger

from src.worker.app import app

logger = get_task_logger(__name__)


@app.task(name="src.worker.tasks.stats.send_daily_report")
def send_daily_report():
    return _run_async(_send_daily_report())


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _send_daily_report():
    from src.db.base import async_session_factory
    from src.db.models.user import User
    from src.db.models.transcription import Transcription
    from src.db.models.transaction import Transaction
    from sqlalchemy import select, func
    from src.config import settings
    from src.services.notification import send_message

    yesterday = datetime.utcnow() - timedelta(days=1)

    async with async_session_factory() as session:
        new_users = await session.scalar(
            select(func.count(User.id)).where(User.created_at >= yesterday)
        )
        transcriptions = await session.scalar(
            select(func.count(Transcription.id)).where(
                Transcription.created_at >= yesterday,
                Transcription.status == "done",
            )
        )
        total_duration = await session.scalar(
            select(func.sum(Transcription.duration_seconds)).where(
                Transcription.created_at >= yesterday,
                Transcription.status == "done",
            )
        ) or 0
        payments = await session.execute(
            select(func.count(Transaction.id), func.sum(Transaction.amount_rub)).where(
                Transaction.created_at >= yesterday,
                Transaction.status == "success",
                Transaction.type.in_(["subscription", "topup"]),
            )
        )
        payment_row = payments.first()
        payment_count = payment_row[0] if payment_row else 0
        payment_sum = payment_row[1] or 0

    hours = (total_duration or 0) // 3600
    date_str = yesterday.strftime("%d.%m.%Y")
    report = (
        f"📊 <b>Статистика за {date_str}</b>\n\n"
        f"👤 Новых пользователей: {new_users}\n"
        f"💰 Оплат: {payment_count} на {payment_sum:,.0f}₽\n"
        f"🎙 Транскрибаций: {transcriptions} (общая длительность: {hours} ч)\n"
    )

    for admin_id in settings.admin_ids_list:
        try:
            await send_message(admin_id, report, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send report to {admin_id}: {e}")
