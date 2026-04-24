"""Singleton Bot + Dispatcher wiring.

Must live in a module *other* than the `python -m src.bot.main` entry point:
when you run a module via `-m`, Python executes it as `__main__`, and any
later `from src.bot.main import dp, bot` re-executes the file as a second
module `src.bot.main`. That second execution calls `include_router` on
router objects whose `parent_router` is already set, which aiogram rejects
with "Router is already attached".

Everything mutable (the Bot, the Dispatcher, middleware and router wiring)
lives here so there is exactly one module object regardless of entry point.
`src.bot.main` just imports from here and drives either polling or uvicorn.
"""
import sentry_sdk

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from src.config import settings
from src.utils.logging import _sentry_before_send, get_logger, setup_logging

setup_logging()
log = get_logger(__name__)

from src.bot.handlers import (  # noqa: E402  (must follow setup_logging)
    about,
    admin,
    callbacks,
    links,
    media,
    menu_router,
    payment,
    profile,
    promo,
    referral,
    settings as settings_handler,
    start,
    test_payment,
    user_settings,
)
from src.bot.middlewares.ban import BanMiddleware  # noqa: E402
from src.bot.middlewares.consent import ConsentMiddleware  # noqa: E402
from src.bot.middlewares.database import DatabaseMiddleware  # noqa: E402
from src.bot.middlewares.rate_limit import RateLimitMiddleware  # noqa: E402
from src.bot.middlewares.user import UserMiddleware  # noqa: E402

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=_sentry_before_send,
    )

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# FSM on a dedicated Redis DB so broker back-pressure cannot evict user state.
storage = RedisStorage.from_url(settings.redis_fsm_url)
dp = Dispatcher(storage=storage)

# Middleware order:
#  1. DatabaseMiddleware — opens a session all later steps reuse.
#  2. UserMiddleware — loads/creates the User row.
#  3. BanMiddleware — stops banned users before rate-limit counters tick up.
#  4. ConsentMiddleware — gate on 152-ФЗ consent (runs after we know who).
#  5. RateLimitMiddleware — last so genuine rate-limit rejections are observable.
dp.update.middleware(DatabaseMiddleware())
dp.update.middleware(UserMiddleware())
dp.update.middleware(BanMiddleware())
dp.update.middleware(ConsentMiddleware())
dp.update.middleware(RateLimitMiddleware())

dp.include_router(start.router)
dp.include_router(about.router)
dp.include_router(profile.router)
dp.include_router(payment.router)
dp.include_router(test_payment.router)
dp.include_router(referral.router)
dp.include_router(promo.router)
dp.include_router(admin.router)
dp.include_router(settings_handler.router)
dp.include_router(user_settings.router)
dp.include_router(menu_router.router)
dp.include_router(links.router)
dp.include_router(media.router)
dp.include_router(callbacks.router)
