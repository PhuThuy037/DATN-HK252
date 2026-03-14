from __future__ import annotations

import os
import time
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "30"))

ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "admin.suggest.apply@test.com").strip().lower()
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "123456")
ADMIN_NAME = os.getenv("TEST_ADMIN_NAME", "Admin Suggest Apply")


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
        json={"name": f"Suggestion Apply FS Co {int(time.time())}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"create rule set failed: HTTP {r.status_code}\n{r.text}")
    cid = str((r.json().get("data") or {}).get("id") or "")
    if not cid:
        fail("rule_set id missing")
    return cid


def generate_suggestion(client: httpx.Client, token: str, rule_set_id: str) -> dict[str, Any]:
    payload = {
        "prompt": "Táº¡o rule block ná»™i dung tÃ i chÃ­nh ná»™i bá»™ trong ngá»¯ cáº£nh office cÃ³ tá»« khÃ³a stk"
    }
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/generate",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"generate suggestion failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def edit_suggestion(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    suggestion_id: str,
    expected_version: int,
) -> dict[str, Any]:
    payload = {
        "expected_version": expected_version,
        "draft": {
            "rule": {
                "stable_key": f"personal.custom.office.finance.block.{int(time.time())}",
                "name": "Block office finance by context",
                "description": "e2e apply+full-scan test",
                "scope": "prompt",
                "conditions": {
                    "all": [
                        {"signal": {"field": "persona", "equals": "office"}},
                        {"signal": {"field": "risk_boost", "gte": 0.1}},
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["stk"],
                            }
                        },
                    ]
                },
                "action": "block",
                "severity": "medium",
                "priority": 250,
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [
                {
                    "entity_type": "PERSONA_OFFICE",
                    "term": "ke toan",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                }
            ],
        },
    }
    r = client.patch(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"edit suggestion failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def confirm_suggestion(
    client: httpx.Client, token: str, rule_set_id: str, suggestion_id: str
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/confirm",
        json={"reason": "confirm for e2e"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"confirm suggestion failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def apply_suggestion(
    client: httpx.Client, token: str, rule_set_id: str, suggestion_id: str
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/apply",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"apply suggestion failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def list_rule_set_rules(
    client: httpx.Client, token: str, rule_set_id: str
) -> list[dict[str, Any]]:
    r = client.get(
        f"{V1}/rule-sets/{rule_set_id}/rules",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"list rule-set rules failed: HTTP {r.status_code}\n{r.text}")
    return list(r.json().get("data") or [])


def full_scan(client: httpx.Client, token: str, rule_set_id: str, text: str) -> dict[str, Any]:
    r = client.post(
        f"{V1}/debug/full-scan",
        json={"rule_set_id": rule_set_id, "text": text},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"full-scan failed: HTTP {r.status_code}\n{r.text}")
    return r.json()


def main() -> None:
    with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
        print("[1/8] register/login")
        register_if_needed(client)
        token = login(client)

        print("[2/8] create rule set")
        rule_set_id = create_rule_set(client, token)
        print(f"rule_set_id={rule_set_id}")

        print("[3/8] generate suggestion")
        generated = generate_suggestion(client, token, rule_set_id)
        suggestion_id = str(generated.get("id") or "")
        if not suggestion_id:
            fail(f"missing suggestion_id: {generated}")

        print("[4/8] edit suggestion to deterministic office/stk block rule")
        edited = edit_suggestion(
            client,
            token,
            rule_set_id,
            suggestion_id,
            expected_version=int(generated.get("version") or 1),
        )
        stable_key = str((((edited.get("draft") or {}).get("rule") or {}).get("stable_key")) or "")
        if not stable_key:
            fail(f"missing stable_key after edit: {edited}")

        print("[5/8] confirm + apply")
        confirmed = confirm_suggestion(client, token, rule_set_id, suggestion_id)
        if str(confirmed.get("status") or "") != "approved":
            fail(f"suggestion not approved: {confirmed}")
        applied = apply_suggestion(client, token, rule_set_id, suggestion_id)
        rule_id = str(applied.get("rule_id") or "")
        if not rule_id:
            fail(f"missing rule_id from apply: {applied}")

        print("[6/8] verify rule exists in rule-set rules")
        rules = list_rule_set_rules(client, token, rule_set_id)
        target_rules = [r for r in rules if str(r.get("id") or "") == rule_id]
        if not target_rules:
            fail(f"applied rule_id not found in list rules: {rule_id}")
        if str(target_rules[0].get("stable_key") or "") != stable_key:
            fail(
                "stable_key mismatch after apply: "
                f"expected={stable_key}, got={target_rules[0].get('stable_key')}"
            )

        print("[7/8] full-scan positive should match and block")
        pos = full_scan(
            client,
            token,
            rule_set_id,
            "Phong ke toan dang cap nhat stk noi bo cho doi soat",
        )
        if str(pos.get("final_action") or "") != "block":
            fail(f"expected full-scan block, got={pos}")
        matched = list(pos.get("matched_rules") or [])
        if not any(str(m.get("rule_id") or "") == rule_id for m in matched):
            fail(f"expected matched_rules contains rule_id={rule_id}, got={matched}")

        print("[8/8] full-scan negative should allow")
        neg = full_scan(
            client,
            token,
            rule_set_id,
            "Hom nay troi dep va team hop sprint planning",
        )
        if str(neg.get("final_action") or "") != "allow":
            fail(f"expected full-scan allow, got={neg}")

    print("ALL PASS: suggestion apply -> company rule -> full-scan works end-to-end.")


if __name__ == "__main__":
    main()





