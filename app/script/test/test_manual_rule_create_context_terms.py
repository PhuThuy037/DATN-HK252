from __future__ import annotations

import os
import time
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "30"))
PWD = os.getenv("TEST_USER_PASSWORD", "123456")


def fail(msg: str) -> None:
    raise AssertionError(msg)


def auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "accept": "application/json",
        "content-type": "application/json",
    }


def register_and_login_fresh_user(client: httpx.Client) -> str:
    now = int(time.time())
    email = f"manual.rule.ctx.{now}@test.com"
    name = f"Manual Rule Ctx {now}"

    r = client.post(
        f"{V1}/auth/register",
        json={"email": email, "password": PWD, "name": name},
    )
    if r.status_code not in (200, 201, 409):
        fail(f"register failed: HTTP {r.status_code}\n{r.text}")

    r = client.post(
        f"{V1}/auth/login",
        json={"email": email, "password": PWD},
    )
    if r.status_code != 200:
        fail(f"login failed: HTTP {r.status_code}\n{r.text}")
    token = str((r.json().get("data") or {}).get("access_token") or "").strip()
    if not token:
        fail("missing access_token")
    return token


def create_rule_set(client: httpx.Client, token: str) -> str:
    r = client.post(
        f"{V1}/rule-sets",
        json={"name": f"Manual Rule Context Terms {int(time.time())}"},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"create rule set failed: HTTP {r.status_code}\n{r.text}")
    out = r.json().get("data") or {}
    rule_set_id = str(out.get("id") or "").strip()
    if not rule_set_id:
        fail("missing rule_set_id")
    return rule_set_id


def create_manual_rule(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rules",
        json=payload,
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"create manual rule failed: HTTP {r.status_code}\n{r.text}")
    out = r.json().get("data") or {}
    if not str(out.get("id") or "").strip():
        fail(f"missing rule id in create response: {out}")
    return out


def debug_evaluate(client: httpx.Client, token: str, content: str) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rules/debug/evaluate",
        json={"content": content},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"debug evaluate failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def main() -> None:
    with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
        print("[1/5] register/login fresh user and create personal rule set")
        token = register_and_login_fresh_user(client)
        rule_set_id = create_rule_set(client, token)

        print("[2/5] create manual rule with legacy payload (no context_terms)")
        legacy_payload = {
            "stable_key": f"personal.custom.manual.legacy.{int(time.time())}",
            "name": "Legacy manual create",
            "description": "legacy raw dsl",
            "scope": "prompt",
            "conditions": {"entity_type": "PHONE"},
            "action": "mask",
            "severity": "medium",
            "priority": 0,
            "rag_mode": "off",
            "enabled": True,
        }
        legacy_created = create_manual_rule(client, token, rule_set_id, legacy_payload)
        if list(legacy_created.get("context_term_ids") or []):
            fail(f"legacy create should not create context terms by default: {legacy_created}")

        print("[3/5] create manual rule with new payload {rule, context_terms}")
        token_term = "ZXQ-MANUAL-123"
        new_payload = {
            "rule": {
                "stable_key": f"personal.custom.manual.internal_code.{int(time.time())}",
                "name": "Mask internal code manual",
                "description": "mask exact token via context term",
                "scope": "prompt",
                "conditions": {
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": [token_term.lower()],
                            }
                        }
                    ]
                },
                "action": "mask",
                "severity": "medium",
                "priority": 0,
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [
                {
                    "entity_type": "INTERNAL_CODE",
                    "term": token_term.lower(),
                    "lang": "vi",
                    "weight": 1,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                }
            ],
        }
        created = create_manual_rule(client, token, rule_set_id, new_payload)
        created_rule_id = str(created.get("id") or "")
        context_term_ids = list(created.get("context_term_ids") or [])
        if not context_term_ids:
            fail(f"new create should return context_term_ids: {created}")

        print("[4/5] debug evaluate positive sample should match created rule")
        eval_pos = debug_evaluate(client, token, f"Toi co ma noi bo {token_term.lower()}")
        matched = list(eval_pos.get("matched_rules") or [])
        matched_ids = [str(x.get("rule_id") or "") for x in matched]
        if created_rule_id not in matched_ids:
            fail(f"created internal-code rule should match positive sample: {eval_pos}")

        print("[5/5] signals should contain context keyword from context_terms runtime")
        signals = dict(eval_pos.get("signals") or {})
        kws = [str(x).strip().lower() for x in list(signals.get("context_keywords") or [])]
        if token_term.lower() not in kws:
            fail(f"context_keywords should include token from context_terms: signals={signals}")

    print("ALL PASS: manual create with optional context_terms works.")


if __name__ == "__main__":
    main()
