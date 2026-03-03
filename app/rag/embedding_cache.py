from __future__ import annotations

import hashlib
import json
from typing import Optional, Sequence

import redis.asyncio as redis

from app.core.config import get_settings

_settings = get_settings()

_redis: Optional[redis.Redis] = None


def _get_redis() -> Optional[redis.Redis]:
    global _redis

    if not _settings.redis_url:
        return None

    if _redis is None:
        _redis = redis.from_url(
            _settings.redis_url,
            decode_responses=True,
        )
    return _redis


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_key(*, model: str, text: str) -> str:
    return f"rag:emb:{model}:{_sha256(text)}"


async def get_embedding_from_cache(key: str) -> Optional[list[float]]:
    r = _get_redis()
    if not r:
        return None

    try:
        v = await r.get(key)
        if not v:
            return None
        arr = json.loads(v)
        if isinstance(arr, list):
            return [float(x) for x in arr]
    except Exception:
        return None

    return None


async def set_embedding_cache(
    key: str,
    emb: Sequence[float],
    ttl_seconds: int = 7 * 86400,  # 7 ngày
) -> None:
    r = _get_redis()
    if not r:
        return

    try:
        await r.set(key, json.dumps(list(emb)), ex=ttl_seconds)
    except Exception:
        pass