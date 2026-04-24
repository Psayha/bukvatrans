import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from src.api.webhooks import handle_yukassa_webhook
from src.config import settings
from src.utils import metrics
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


@app.middleware("http")
async def _prometheus_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    # Path-cardinality control: only label metrics with known endpoints.
    path = request.url.path
    if path not in ("/webhooks/telegram", "/webhooks/yukassa", "/health", "/metrics"):
        path = "other"
    metrics.http_requests_total.labels(path=path, status=str(response.status_code)).inc()
    metrics.http_request_duration_seconds.labels(path=path).observe(elapsed)
    return response


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    body, content_type = metrics.render_latest()
    return Response(content=body, media_type=content_type)


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

    from src.bot.dispatcher import dp, bot
    from aiogram.types import Update

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}
