from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.webhooks import handle_yukassa_webhook

app = FastAPI(title="TranscribeBot API", version="1.0.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/webhooks/yukassa")
async def yukassa_webhook(request: Request) -> JSONResponse:
    return await handle_yukassa_webhook(request)


@app.post("/webhooks/telegram")
async def telegram_webhook(request: Request) -> dict:
    """Telegram webhook endpoint — handled by aiogram dispatcher."""
    from src.bot.main import dp, bot
    from aiogram.types import Update
    import json

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}
