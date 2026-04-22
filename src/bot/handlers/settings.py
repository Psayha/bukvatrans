from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.inline import language_kb
from src.bot.texts.ru import (
    CANCEL_NO_TASK,
    CANCEL_SUCCESS,
    LANGUAGE_PROMPT,
    PRIVACY_SHORT,
    TERMS_SHORT,
)
from src.config import settings
from src.db.models.transcription import Transcription
from src.db.models.user import User

router = Router()


@router.message(Command("language"))
async def cmd_language(message: Message) -> None:
    await message.answer(LANGUAGE_PROMPT, reply_markup=language_kb())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, user: User, session: AsyncSession) -> None:
    """Cancel the most recent still-running transcription for this user.

    The status transition + refund runs in a single transaction with a row
    lock on the transcription. That way, if the worker is already running
    `_refund_and_notify` concurrently, exactly one of them wins and the
    other sees status != pending/processing and skips the refund.
    """
    # Make sure any autobegin tx from earlier middleware is closed, so the
    # `session.begin()` below doesn't trip "already active".
    await session.rollback()

    revoked_task_id: str | None = None
    refunded = False
    try:
        async with session.begin():
            # Find the most recent in-flight job AND lock it.
            stmt = (
                select(Transcription)
                .where(
                    Transcription.user_id == user.id,
                    Transcription.status.in_(["pending", "processing"]),
                )
                .order_by(Transcription.created_at.desc())
                .limit(1)
                .with_for_update()
            )
            try:
                result = await session.execute(stmt)
            except Exception:
                # SQLite doesn't support FOR UPDATE; fall back to plain read.
                result = await session.execute(
                    select(Transcription)
                    .where(
                        Transcription.user_id == user.id,
                        Transcription.status.in_(["pending", "processing"]),
                    )
                    .order_by(Transcription.created_at.desc())
                    .limit(1)
                )
            t = result.scalar_one_or_none()
            if not t:
                # Nothing to cancel. Exit without touching state — the
                # enclosing session.begin() will commit a no-op.
                await message.answer(CANCEL_NO_TASK)
                return

            t.status = "cancelled"
            revoked_task_id = t.celery_task_id

            if (t.seconds_charged or 0) > 0:
                # Row-lock the user too so concurrent credits serialize.
                try:
                    locked = await session.get(User, user.id, with_for_update=True)
                except Exception:
                    locked = await session.get(User, user.id)
                if locked is not None:
                    locked.balance_seconds = (locked.balance_seconds or 0) + t.seconds_charged
                    refunded = True
    except Exception:
        # Transaction rolled back; surface a generic error, don't leak details.
        await message.answer("❌ Не удалось отменить задачу. Попробуйте ещё раз.")
        return

    # Best-effort revoke happens AFTER commit so we don't try to cancel a
    # Celery task for a transition that ended up rolled back.
    if revoked_task_id:
        try:
            from src.worker.app import app as celery_app
            celery_app.control.revoke(revoked_task_id, terminate=False)
        except Exception:
            pass

    await message.answer(CANCEL_SUCCESS if not refunded else CANCEL_SUCCESS)


@router.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    await message.answer(
        PRIVACY_SHORT.format(
            retention=settings.TRANSCRIPTION_RETENTION_DAYS,
            url=settings.PRIVACY_POLICY_URL or "—",
            email=settings.SUPPORT_EMAIL,
        ),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("terms"))
async def cmd_terms(message: Message) -> None:
    await message.answer(
        TERMS_SHORT.format(
            url=settings.TERMS_URL or "—",
            email=settings.SUPPORT_EMAIL,
        ),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
