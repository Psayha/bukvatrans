"""Admin handlers — grouped into focused submodules to keep each file
readable (< 150 lines). `router` aggregates every submodule's router and
is what the main dispatcher mounts.
"""
from aiogram import Router

from src.bot.handlers.admin import (
    approval,
    broadcast,
    menu,
    models,
    promo,
    stats,
    testing,
    users,
)

router = Router()
router.include_router(menu.router)
router.include_router(stats.router)
router.include_router(users.router)
router.include_router(promo.router)
router.include_router(broadcast.router)
router.include_router(testing.router)
router.include_router(models.router)
router.include_router(approval.router)

__all__ = ["router"]
