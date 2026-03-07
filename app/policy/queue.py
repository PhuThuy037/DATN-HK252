from __future__ import annotations

from uuid import UUID

import redis

from app.common.error_codes import ErrorCode
from app.common.errors import AppError
from app.core.config import get_settings


def get_policy_ingest_queue_name() -> str:
    settings = get_settings()
    name = (settings.policy_ingest_queue_name or "").strip()
    return name or "policy_ingest_jobs"


def enqueue_policy_ingest_job(*, job_id: UUID) -> None:
    settings = get_settings()
    redis_url = (settings.redis_url or "").strip()
    if not redis_url:
        raise AppError(
            500,
            ErrorCode.INTERNAL_ERROR,
            "REDIS_URL is required for background ingest",
            details=[{"field": "redis_url", "reason": "missing"}],
        )

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    try:
        client.lpush(get_policy_ingest_queue_name(), str(job_id))
    finally:
        client.close()
