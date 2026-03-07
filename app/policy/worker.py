from __future__ import annotations

import time
from uuid import UUID

import redis
from sqlmodel import Session

from app.core.config import get_settings
from app.db.engine import engine
from app.policy.queue import get_policy_ingest_queue_name
from app.policy.service import process_policy_ingest_job


def _get_redis_client() -> redis.Redis:
    settings = get_settings()
    redis_url = (settings.redis_url or "").strip()
    if not redis_url:
        raise RuntimeError("REDIS_URL is required for policy ingest worker")
    return redis.Redis.from_url(redis_url, decode_responses=True)


def run_worker_loop(*, sleep_seconds: float = 1.0) -> None:
    queue_name = get_policy_ingest_queue_name()
    client = _get_redis_client()
    print(f"[policy-ingest-worker] started, queue={queue_name}")
    try:
        while True:
            popped = client.brpop(queue_name, timeout=5)
            if not popped:
                time.sleep(sleep_seconds)
                continue

            _, job_id_raw = popped
            try:
                job_id = UUID(str(job_id_raw))
            except Exception:
                print(
                    f"[policy-ingest-worker] skip invalid job id from queue: {job_id_raw}"
                )
                continue

            try:
                with Session(engine) as session:
                    process_policy_ingest_job(session=session, job_id=job_id)
            except Exception as e:
                print(f"[policy-ingest-worker] job={job_id} failed: {e}")
    finally:
        client.close()


def main() -> None:
    run_worker_loop()


if __name__ == "__main__":
    main()
