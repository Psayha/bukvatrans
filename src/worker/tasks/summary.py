import asyncio
from celery.utils.log import get_task_logger

from src.worker.app import app

logger = get_task_logger(__name__)


@app.task(
    bind=True,
    name="src.worker.tasks.summary.summary_task",
    queue="summary",
    max_retries=3,
)
def summary_task(self, transcription_id: str, user_id: int) -> dict:
    return asyncio.get_event_loop().run_until_complete(
        _summary_async(transcription_id, user_id)
    )


async def _summary_async(transcription_id: str, user_id: int) -> dict:
    from src.db.base import async_session_factory
    from src.db.repositories.transcription import get_transcription, update_transcription_status
    from src.services.summary import generate_summary
    from src.services.notification import send_message
    from src.bot.texts.ru import SUMMARY_READY, SUMMARY_ERROR

    async with async_session_factory() as session:
        transcription = await get_transcription(transcription_id, session)
        if not transcription or not transcription.result_text:
            await send_message(user_id, SUMMARY_ERROR)
            return {"status": "failed"}

        try:
            summary = await generate_summary(transcription.result_text)
            transcription.summary_text = summary
            await session.commit()
        except Exception as e:
            logger.error(f"Summary error: {e}", exc_info=True)
            await send_message(user_id, SUMMARY_ERROR)
            return {"status": "failed", "error": str(e)}

    await send_message(user_id, SUMMARY_READY.format(summary=summary), parse_mode="HTML")
    return {"status": "done"}


@app.task(
    bind=True,
    name="src.worker.tasks.summary.docx_task",
    queue="summary",
)
def docx_task(self, transcription_id: str, user_id: int) -> dict:
    return asyncio.get_event_loop().run_until_complete(
        _docx_async(transcription_id, user_id)
    )


async def _docx_async(transcription_id: str, user_id: int) -> dict:
    from src.db.base import async_session_factory
    from src.db.repositories.transcription import get_transcription
    from src.services.notification import send_document
    from docx import Document
    import io

    async with async_session_factory() as session:
        transcription = await get_transcription(transcription_id, session)
        if not transcription or not transcription.result_text:
            return {"status": "failed"}

    doc = Document()
    doc.add_heading("Транскрибация", 0)
    for para in transcription.result_text.split("\n"):
        doc.add_paragraph(para)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    await send_document(user_id, buf.read(), "transcription.docx")
    return {"status": "done"}
