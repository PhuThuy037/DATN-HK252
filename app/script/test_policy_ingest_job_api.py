from __future__ import annotations

import os
import time
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
TIMEOUT = float(os.getenv("API_TIMEOUT_SECONDS", "30"))

ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "admin.policy@test.com").strip().lower()
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "123456")
ADMIN_NAME = os.getenv("TEST_ADMIN_NAME", "Admin Policy")


def fail(msg: str) -> None:
    raise AssertionError(msg)


def register_if_needed(client: httpx.Client) -> None:
    r = client.post(
        f"{V1}/auth/register",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "name": ADMIN_NAME},
    )
    if r.status_code in (200, 201):
        return
    if r.status_code == 409:
        return
    fail(f"register failed: HTTP {r.status_code}\n{r.text}")


def login(client: httpx.Client) -> str:
    r = client.post(
        f"{V1}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if r.status_code != 200:
        fail(f"login failed: HTTP {r.status_code}\n{r.text}")
    body = r.json()
    token = (((body or {}).get("data") or {}).get("access_token") or "").strip()
    if not token:
        fail("login did not return access_token")
    return token


def create_company(client: httpx.Client, token: str) -> str:
    r = client.post(
        f"{V1}/companies",
        json={"name": f"Policy Ingest Co {int(time.time())}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"create company failed: HTTP {r.status_code}\n{r.text}")
    body = r.json()
    company_id = str((body.get("data") or {}).get("id") or "")
    if not company_id:
        fail("create company did not return company id")
    return company_id


def create_job(client: httpx.Client, token: str, company_id: str, content: str) -> str:
    payload = {
        "items": [
            {
                "stable_key": "company.policy.test.alpha",
                "title": "Policy Alpha",
                "doc_type": "policy",
                "content": content,
                "enabled": True,
            }
        ]
    }
    r = client.post(
        f"{V1}/companies/{company_id}/policy-ingest-jobs",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"create ingest job failed: HTTP {r.status_code}\n{r.text}")
    body = r.json()
    job_id = str(((body.get("data") or {}).get("id")) or "")
    if not job_id:
        fail("create ingest job did not return job id")
    return job_id


def wait_job_done(
    client: httpx.Client, token: str, company_id: str, job_id: str, timeout_sec: float = 20.0
) -> dict[str, Any]:
    started = time.time()
    while time.time() - started <= timeout_sec:
        r = client.get(
            f"{V1}/companies/{company_id}/policy-ingest-jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code != 200:
            fail(f"get ingest job failed: HTTP {r.status_code}\n{r.text}")
        body = r.json()
        data = body.get("data") or {}
        status = str(data.get("status") or "").lower()
        if status in ("success", "failed"):
            return data
        time.sleep(0.5)
    fail("timeout waiting policy ingest job to finish")


def list_docs(client: httpx.Client, token: str, company_id: str) -> list[dict[str, Any]]:
    r = client.get(
        f"{V1}/companies/{company_id}/policy-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"list policy docs failed: HTTP {r.status_code}\n{r.text}")
    body = r.json()
    return list((body.get("data") or []))


def main() -> None:
    with httpx.Client(timeout=TIMEOUT) as client:
        print("[1/6] register/login admin")
        register_if_needed(client)
        token = login(client)

        print("[2/6] create company")
        company_id = create_company(client, token)
        print(f"company_id={company_id}")

        print("[3/6] create ingest job #1 (new doc)")
        job1 = create_job(client, token, company_id, "alpha short policy text")
        detail1 = wait_job_done(client, token, company_id, job1)
        if detail1.get("status") != "success":
            fail(f"job1 expected success, got {detail1.get('status')}\n{detail1}")

        print("[4/6] create ingest job #2 (same hash -> skipped)")
        job2 = create_job(client, token, company_id, "alpha short policy text")
        detail2 = wait_job_done(client, token, company_id, job2)
        if detail2.get("status") != "success":
            fail(f"job2 expected success, got {detail2.get('status')}\n{detail2}")
        if int(detail2.get("skipped_items") or 0) < 1:
            fail(f"job2 expected skipped_items >= 1, got {detail2}")

        print("[5/6] create ingest job #3 (same key, new hash -> update)")
        job3 = create_job(client, token, company_id, "alpha short policy text v2")
        detail3 = wait_job_done(client, token, company_id, job3)
        if detail3.get("status") != "success":
            fail(f"job3 expected success, got {detail3.get('status')}\n{detail3}")
        if int(detail3.get("success_items") or 0) < 1:
            fail(f"job3 expected success_items >= 1, got {detail3}")

        print("[6/6] verify document version moved to 2")
        docs = list_docs(client, token, company_id)
        target = [d for d in docs if d.get("stable_key") == "company.policy.test.alpha"]
        if len(target) != 1:
            fail(f"expected exactly 1 target doc, got={len(target)} docs={docs}")
        if int(target[0].get("version") or 0) < 2:
            fail(f"expected version >= 2 after update, got={target[0].get('version')}")

    print("ALL PASS: policy ingest jobs (idempotent + update) are working.")


if __name__ == "__main__":
    main()
