from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User
from src.db.repositories.transcription import create_transcription
from src.db.repositories.user import decrement_free_uses
from src.services.billing import check_can_transcribe
from src.utils.validators import is_allowed_url
from src.bot.texts.ru import (
    PROCESSING, URL_NOT_SUPPORTED, INSUFFICIENT_BALANCE,
)
from src.bot.keyboards.inline import subscribe_kb

router = Router()

URL_SOURCE_MAP = {
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "rutube.ru": "rutube",
    "drive.google.com": "gdrive",
    "disk.yandex.ru": "yadisk",
    "yadi.sk": "yadisk",
    "vk.com": "vk",
    "vkvideo.ru": "vk",
    "ok.ru": "ok",
}


def _detect_source_type(url: str) -> str:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower().replace("www.", "")
    for d, source in URL_SOURCE_MAP.items():
        if domain == d or domain.endswith("." + d):
            return source
    return "youtube"


@router.message(F.text.regexp(r"https?://\S+"))
async def handle_url(message: Message, user: User, session: AsyncSession) -> None:
    url = message.text.strip()

    if not is_allowed_url(url):
        await message.answer(URL_NOT_SUPPORTED)
        return

    can, reason = await check_can_transcribe(user)
    if not can:
        await message.answer(
            INSUFFICIENT_BALANCE.format(reason=reason),
            reply_markup=subscribe_kb(),
            parse_mode="HTML",
        )
        return

    source_type = _detect_source_type(url)
    is_free = user.free_uses_left > 0

    transcription = await create_transcription(
        user_id=user.id,
        source_type=source_type,
        session=session,
        source_url=url,
        is_free=is_free,
    )

    if is_free:
        await decrement_free_uses(user.id, session)

    from src.worker.tasks.transcription import transcribe_task
    transcribe_task.delay(
        transcription_id=transcription.id,
        user_id=user.id,
        source_url=url,
        source_type=source_type,
    )

    await message.answer(
        PROCESSING.format(eta="2-10 мин", position=1),
        parse_mode="HTML",
    )
