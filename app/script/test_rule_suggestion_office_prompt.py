from __future__ import annotations

import os
import time

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "30"))

ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "admin.suggest.office@test.com").strip().lower()
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "123456")
ADMIN_NAME = os.getenv("TEST_ADMIN_NAME", "Admin Suggest Office")


def fail(msg: str) -> None:
    raise AssertionError(msg)


def register_if_needed(client: httpx.Client) -> None:
    r = client.post(
        f"{V1}/auth/register",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "name": ADMIN_NAME},
    )
    if r.status_code in (200, 201, 409):
        return
    fail(f"register failed: HTTP {r.status_code}\n{r.text}")


def login(client: httpx.Client) -> str:
    r = client.post(
        f"{V1}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if r.status_code != 200:
        fail(f"login failed: HTTP {r.status_code}\n{r.text}")
    token = str((((r.json().get("data") or {}).get("access_token")) or "")).strip()
    if not token:
        fail("missing access token")
    return token


def create_company(client: httpx.Client, token: str) -> str:
    r = client.post(
        f"{V1}/companies",
        json={"name": f"Suggestion Office Co {int(time.time())}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"create company failed: HTTP {r.status_code}\n{r.text}")
    cid = str((r.json().get("data") or {}).get("id") or "")
    if not cid:
        fail("company id missing")
    return cid


def main() -> None:
    with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
        print("[1/3] register/login + create company")
        register_if_needed(client)
        token = login(client)
        company_id = create_company(client, token)

        print("[2/3] generate office/hr prompt")
        payload = {
            "prompt": "Tạo rule block nội dung HR nội bộ liên quan lương, hợp đồng, nhân sự trong ngữ cảnh office"
        }
        r = client.post(
            f"{V1}/companies/{company_id}/rule-suggestions/generate",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code != 200:
            fail(f"generate failed: HTTP {r.status_code}\n{r.text}")
        out = r.json().get("data") or {}
        rule = ((out.get("draft") or {}).get("rule") or {})
        cond = rule.get("conditions") or {}

        print("[3/3] verify not fallback PHONE and has office signal")
        as_text = str(cond)
        if "PHONE" in as_text:
            fail(f"unexpected PHONE fallback in conditions: {cond}")
        if "persona" not in as_text or "office" not in as_text:
            fail(f"expected office persona signal in conditions: {cond}")

    print("ALL PASS: office/hr prompt no longer falls back to PHONE.")


if __name__ == "__main__":
    main()
