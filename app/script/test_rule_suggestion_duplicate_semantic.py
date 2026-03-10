from __future__ import annotations

import os
import time
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "30"))

ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "admin.suggest.semantic@test.com").strip().lower()
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "123456")
ADMIN_NAME = os.getenv("TEST_ADMIN_NAME", "Admin Suggest Semantic")


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


def create_rule_set(client: httpx.Client, token: str) -> str:
    r = client.post(
        f"{V1}/rule-sets",
        json={"name": f"Suggestion Semantic Co {int(time.time())}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"create rule set failed: HTTP {r.status_code}\n{r.text}")
    cid = str((r.json().get("data") or {}).get("id") or "")
    if not cid:
        fail("rule_set id missing")
    return cid


def create_rule_set_rule(
    client: httpx.Client, token: str, rule_set_id: str, stable_key: str
) -> dict[str, Any]:
    payload = {
        "stable_key": stable_key,
        "name": "Block PHONE semantic baseline",
        "description": "seed semantic duplicate baseline",
        "scope": "prompt",
        "conditions": {"any": [{"entity_type": "PHONE"}]},
        "action": "block",
        "severity": "medium",
        "priority": 120,
        "rag_mode": "off",
        "enabled": True,
    }
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rules",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"create rule set rule failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def generate(client: httpx.Client, token: str, rule_set_id: str, prompt: str) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/generate",
        json={"prompt": prompt},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"generate failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def main() -> None:
    with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
        print("[1/4] register/login admin")
        register_if_needed(client)
        token = login(client)

        print("[2/4] create rule set and baseline rule")
        rule_set_id = create_rule_set(client, token)
        stable_key = "company.custom.phone.block.semantic"
        baseline = create_rule_set_rule(client, token, rule_set_id, stable_key)
        if str(baseline.get("stable_key") or "") != stable_key:
            fail(f"unexpected baseline stable_key: {baseline}")

        print("[3/4] generate suggestion and inspect duplicate_check")
        out = generate(
            client,
            token,
            rule_set_id,
            "Tao rule block so dien thoai, uu tien cao, bo sung context hotline",
        )
        duplicate_check = out.get("duplicate_check") or {}
        candidates = list(duplicate_check.get("candidates") or [])
        if not candidates:
            fail(f"duplicate_check candidates should not be empty: {out}")

        matched = [
            c for c in candidates if str(c.get("stable_key") or "").strip() == stable_key
        ]
        if not matched:
            fail(
                "duplicate_check did not include baseline stable_key "
                f"{stable_key}; candidates={candidates}"
            )

        decision = str(duplicate_check.get("decision") or "")
        if decision not in {"EXACT_DUPLICATE", "NEAR_DUPLICATE", "DIFFERENT"}:
            fail(f"invalid duplicate decision: {decision}")

        print("[4/4] verify duplicate_check contract fields")
        if int(duplicate_check.get("top_k") or 0) != 5:
            fail(f"expected top_k=5, got {duplicate_check.get('top_k')}")
        if float(duplicate_check.get("exact_threshold") or 0) <= 0:
            fail(f"missing exact_threshold: {duplicate_check}")
        if float(duplicate_check.get("near_threshold") or 0) <= 0:
            fail(f"missing near_threshold: {duplicate_check}")
        if not str(duplicate_check.get("source") or ""):
            fail(f"missing duplicate source: {duplicate_check}")

    print("ALL PASS: semantic duplicate check response is working.")


if __name__ == "__main__":
    main()



