from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from src.api.webhooks import handle_yukassa_webhook
from src.config import settings
from src.utils.logging import _sentry_before_send, get_logger

logger = get_logger(__name__)

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=_sentry_before_send,
        integrations=[FastApiIntegration(), StarletteIntegration()],
    )

app = FastAPI(title="TranscribeBot API", version="1.0.0")

if settings.cors_allowed_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        allow_credentials=False,
    )


@app.get("/health")
async def health() -> JSONResponse:
    """Deep health-check — verifies DB and Redis connectivity."""
    checks: dict[str, str] = {"status": "ok"}
    status_code = 200

    try:
        from sqlalchemy import text
        from src.db.base import async_session_factory
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {type(e).__name__}"
        checks["status"] = "degraded"
        status_code = 503

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.close()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {type(e).__name__}"
        checks["status"] = "degraded"
        status_code = 503

    return JSONResponse(checks, status_code=status_code)


@app.post("/webhooks/yukassa")
async def yukassa_webhook(request: Request) -> JSONResponse:
    return await handle_yukassa_webhook(request)


@app.post("/webhooks/telegram")
async def telegram_webhook(request: Request) -> dict:
    """Telegram webhook endpoint — validates secret token before dispatching."""
    expected = settings.WEBHOOK_SECRET
    if not expected:
        # Refuse to run in webhook mode without a secret configured
        logger.error("telegram_webhook_missing_secret")
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    # Constant-time comparison
    import hmac
    if not hmac.compare_digest(provided, expected):
        logger.warning("telegram_webhook_bad_secret")
        raise HTTPException(status_code=403, detail="Forbidden")

    from src.bot.main import dp, bot
    from aiogram.types import Update

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}
