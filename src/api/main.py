import time

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from src.api.routes.admin import broadcast as admin_broadcast
from src.api.routes.admin import promo as admin_promo
from src.api.routes.admin import stats as admin_stats
from src.api.routes.admin import transcriptions as admin_transcriptions
from src.api.routes.admin import transactions as admin_transactions
from src.api.routes.admin import users as admin_users
from src.api.routes.v1 import auth as v1_auth
from src.api.routes.v1 import payments as v1_payments
from src.api.routes.v1 import profile as v1_profile
from src.api.routes.v1 import promo as v1_promo
from src.api.routes.v1 import transcriptions as v1_transcriptions
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

app = FastAPI(title="Littera API", version="2.0.0")

# CORS — allow the admin panel (sb.littera.site) and public web app (littera.site).
_cors_origins = settings.cors_allowed_origins_list or []
if not _cors_origins and settings.ENV != "production":
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _prometheus_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    path = request.url.path
    _known = {"/webhooks/telegram", "/webhooks/yukassa", "/health", "/metrics"}
    if path in _known:
        pass
    elif path.startswith("/api/admin"):
        path = "/api/admin"
    elif path.startswith("/api/v1"):
        path = "/api/v1"
    else:
        path = "other"
    metrics.http_requests_total.labels(path=path, status=str(response.status_code)).inc()
    metrics.http_request_duration_seconds.labels(path=path).observe(elapsed)
    return response


_V1 = "/api/v1"
_ADMIN = "/api/admin"

app.include_router(v1_auth.router, prefix=_V1)
app.include_router(v1_profile.router, prefix=_V1)
app.include_router(v1_transcriptions.router, prefix=_V1)
app.include_router(v1_payments.router, prefix=_V1)
app.include_router(v1_promo.router, prefix=_V1)

app.include_router(admin_stats.router, prefix=_ADMIN)
app.include_router(admin_users.router, prefix=_ADMIN)
app.include_router(admin_transcriptions.router, prefix=_ADMIN)
app.include_router(admin_transactions.router, prefix=_ADMIN)
app.include_router(admin_promo.router, prefix=_ADMIN)
app.include_router(admin_broadcast.router, prefix=_ADMIN)


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    body, content_type = metrics.render_latest()
    return Response(content=body, media_type=content_type)


@app.get("/health")
async def health() -> JSONResponse:
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
    import hmac

    expected = settings.WEBHOOK_SECRET
    if not expected:
        logger.error("telegram_webhook_missing_secret")
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(provided, expected):
        logger.warning("telegram_webhook_bad_secret")
        raise HTTPException(status_code=403, detail="Forbidden")

    from aiogram.types import Update

    from src.bot.dispatcher import bot, dp

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}
