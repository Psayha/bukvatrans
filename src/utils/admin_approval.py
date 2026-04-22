"""Two-admin-approval workflow.

Any admin command that mutates user state (balance / ban / unban) is
two-factor: the initiating admin creates a pending request, and a *different*
admin must approve it via an inline button before the action executes.

State lives in Redis (cache DB). Keys:
    admin:approval:{token} = JSON({requester_id, command, args, expires_at})

TTL is enforced both by Redis EXPIRE and by a timestamp guard in Python.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from time import time
from typing import Any, Optional

import redis.asyncio as aioredis

from src.config import settings

_KEY_PREFIX = "admin:approval:"


@dataclass
class ApprovalRequest:
    requester_id: int
    command: str
    args: list[str]
    expires_at: float


def _client() -> aioredis.Redis:
    # Cache DB — same Redis namespace we use for other ephemeral state.
    return aioredis.from_url(settings.redis_cache_url, decode_responses=True)


async def create(requester_id: int, command: str, args: list[str]) -> str:
    """Persist a pending request; return an opaque token for the approval button."""
    token = secrets.token_urlsafe(16)
    expires_at = time() + settings.ADMIN_APPROVAL_TTL_SECONDS
    payload = ApprovalRequest(
        requester_id=requester_id,
        command=command,
        args=args,
        expires_at=expires_at,
    )
    r = _client()
    try:
        await r.set(
            _KEY_PREFIX + token,
            json.dumps(asdict(payload)),
            ex=settings.ADMIN_APPROVAL_TTL_SECONDS,
        )
    finally:
        await r.close()
    return token


async def consume(token: str, approver_id: int) -> Optional[ApprovalRequest]:
    """Atomically fetch and delete the request.

    Returns None if:
      - the token doesn't exist (expired or already consumed)
      - the approver is the same admin who created it (can't self-approve)
    """
    r = _client()
    try:
        raw = await r.getdel(_KEY_PREFIX + token)
    finally:
        await r.close()
    if raw is None:
        return None

    data: dict[str, Any] = json.loads(raw)
    req = ApprovalRequest(**data)
    if req.expires_at < time():
        return None
    if req.requester_id == approver_id:
        # Self-approval defeats the purpose — put it back with remaining TTL
        # so another admin can still approve, then refuse this one.
        remaining = int(req.expires_at - time())
        if remaining > 0:
            r = _client()
            try:
                await r.set(_KEY_PREFIX + token, raw, ex=remaining)
            finally:
                await r.close()
        return None

    return req
