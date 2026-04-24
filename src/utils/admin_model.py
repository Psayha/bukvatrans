"""Runtime override of the active OpenRouter model.

`summary.generate_summary` calls `get_active_model()` on each invocation.
Admins can change the model via /admin_model without restarting anything —
we just flip a Redis key. Falls back to `settings.OPENROUTER_MODEL` when
the key isn't set or Redis is down.
"""
import json
from typing import Optional

import redis.asyncio as aioredis

from src.config import settings

_ACTIVE_KEY = "admin:openrouter_model"
_LIST_KEY_PREFIX = "admin:model_list:"
_LIST_TTL = 600  # 10 min — matches FSM timeout


def _client() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_cache_url, decode_responses=True)


async def get_active_model() -> str:
    """Return override from Redis or the configured default."""
    try:
        r = _client()
        try:
            override = await r.get(_ACTIVE_KEY)
        finally:
            await r.close()
        if override:
            return override
    except Exception:
        # Never crash summary generation because of Redis hiccups.
        pass
    return settings.OPENROUTER_MODEL


async def set_active_model(model: str) -> None:
    r = _client()
    try:
        await r.set(_ACTIVE_KEY, model)
    finally:
        await r.close()


async def save_model_list(admin_id: int, model_ids: list[str]) -> None:
    """Stash a numbered list for the admin's FSM pick."""
    r = _client()
    try:
        await r.set(
            f"{_LIST_KEY_PREFIX}{admin_id}",
            json.dumps(model_ids),
            ex=_LIST_TTL,
        )
    finally:
        await r.close()


async def load_model_list(admin_id: int) -> Optional[list[str]]:
    r = _client()
    try:
        raw = await r.get(f"{_LIST_KEY_PREFIX}{admin_id}")
    finally:
        await r.close()
    return json.loads(raw) if raw else None
