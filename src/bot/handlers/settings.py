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
    """Cancel the most recent still-running transcription for this user."""
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
        await message.answer(CANCEL_NO_TASK)
        return

    # Mark as cancelled so the worker short-circuits if it's still queued; a
    # running task will finish but the result will be discarded below via status
    # check in worker code (not implemented inline — best-effort cancel).
    t.status = "cancelled"
    await session.commit()

    # Revoke the Celery task if we recorded its id.
    if t.celery_task_id:
        try:
            from src.worker.app import app as celery_app
            celery_app.control.revoke(t.celery_task_id, terminate=False)
        except Exception:
            pass

    # Refund any charged seconds.
    if (t.seconds_charged or 0) > 0:
        user.balance_seconds = (user.balance_seconds or 0) + t.seconds_charged
        await session.commit()

    await message.answer(CANCEL_SUCCESS)


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
