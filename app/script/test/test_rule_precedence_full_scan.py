from __future__ import annotations

import os
import sys
import time
import json
import httpx


BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{BASE_URL}/v1"
TIMEOUT = float(os.getenv("API_TIMEOUT_SECONDS", "30"))

ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "admin.rule@test.com").strip().lower()
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "123456")
ADMIN_NAME = os.getenv("TEST_ADMIN_NAME", "Admin Rule")

PHONE_TEXT = "Hotline test la 0901234567"
GLOBAL_PHONE_KEY = "global.pii.phone.mask"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def pretty(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def expect_status(resp: httpx.Response, code: int) -> dict:
    if resp.status_code != code:
        fail(
            f"HTTP {resp.status_code} != {code}\nURL: {resp.request.method} {resp.request.url}\nBODY: {resp.text}"
        )
    return resp.json()


def ensure_ok_api(body: dict, context: str) -> dict:
    if not body.get("ok"):
        fail(f"{context} -> api failed:\n{pretty(body)}")
    return body.get("data")


def register_if_needed(client: httpx.Client) -> None:
    payload = {
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
        "name": ADMIN_NAME,
    }
    r = client.post(f"{V1}/auth/register", json=payload)
    if r.status_code == 200:
        return
    if r.status_code == 409:
        return
    fail(f"register failed: HTTP {r.status_code}\n{r.text}")


def login(client: httpx.Client) -> str:
    payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    body = expect_status(client.post(f"{V1}/auth/login", json=payload), 200)
    data = ensure_ok_api(body, "login")
    token = data.get("access_token")
    if not token:
        fail("missing access_token from login")
    return token


def create_rule_set(client: httpx.Client, token: str) -> str:
    suffix = int(time.time())
    payload = {"name": f"Rule Precedence Test {suffix}"}
    r = client.post(f"{V1}/rule-sets", json=payload, headers=auth_headers(token))
    body = expect_status(r, 200)
    data = ensure_ok_api(body, "create rule set")
    rule_set_id = data.get("id")
    if not rule_set_id:
        fail("missing rule_set_id")
    return rule_set_id


def auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "accept": "application/json",
        "content-type": "application/json",
    }


def list_rules(client: httpx.Client, token: str, rule_set_id: str) -> list[dict]:
    r = client.get(f"{V1}/rule-sets/{rule_set_id}/rules", headers=auth_headers(token))
    body = expect_status(r, 200)
    data = ensure_ok_api(body, "list rules")
    if not isinstance(data, list):
        fail("list rules returned non-list")
    return data


def full_scan(client: httpx.Client, token: str, rule_set_id: str, text: str) -> dict:
    payload = {"text": text, "rule_set_id": rule_set_id}
    r = client.post(
        f"{V1}/debug/full-scan",
        json=payload,
        headers=auth_headers(token),
    )
    body = expect_status(r, 200)
    return body


def stable_keys(scan_body: dict) -> list[str]:
    rows = scan_body.get("matched_rules") or []
    return [str(x.get("stable_key")) for x in rows]


def find_rule_by_key(rules: list[dict], key: str) -> dict | None:
    for r in rules:
        if r.get("stable_key") == key:
            return r
    return None


def toggle_global_phone(
    client: httpx.Client, token: str, rule_set_id: str, enabled: bool
) -> dict:
    payload = {"enabled": enabled}
    r = client.patch(
        f"{V1}/rule-sets/{rule_set_id}/rules/global/{GLOBAL_PHONE_KEY}/enabled",
        json=payload,
        headers=auth_headers(token),
    )
    body = expect_status(r, 200)
    data = ensure_ok_api(body, f"toggle global phone enabled={enabled}")
    return data


def create_custom_phone_block(client: httpx.Client, token: str, rule_set_id: str) -> dict:
    payload = {
        "stable_key": f"personal.test.phone.block.{int(time.time())}",
        "name": "Company custom phone block",
        "description": "custom block for test",
        "scope": "prompt",
        "conditions": {"any": [{"entity_type": "PHONE", "min_score": 0.8}]},
        "action": "block",
        "severity": "high",
        "priority": 220,
        "rag_mode": "off",
        "enabled": True,
    }
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rules",
        json=payload,
        headers=auth_headers(token),
    )
    body = expect_status(r, 200)
    return ensure_ok_api(body, "create custom phone block")


def patch_rule_action(
    client: httpx.Client, token: str, rule_set_id: str, rule_id: str, action: str
) -> httpx.Response:
    return client.patch(
        f"{V1}/rule-sets/{rule_set_id}/rules/{rule_id}",
        json={"action": action},
        headers=auth_headers(token),
    )


def main() -> None:
    with httpx.Client(timeout=TIMEOUT) as client:
        print("[1/8] register/login admin")
        register_if_needed(client)
        token = login(client)

        print("[2/8] create rule set")
        rule_set_id = create_rule_set(client, token)
        print(f"rule_set_id={rule_set_id}")

        print("[3/8] baseline: global phone rule should exist and match")
        rules = list_rules(client, token, rule_set_id)
        if not find_rule_by_key(rules, GLOBAL_PHONE_KEY):
            fail(f"cannot find global key={GLOBAL_PHONE_KEY} in list rules")
        baseline = full_scan(client, token, rule_set_id, PHONE_TEXT)
        if GLOBAL_PHONE_KEY not in stable_keys(baseline):
            fail(f"baseline full-scan should include {GLOBAL_PHONE_KEY}\n{pretty(baseline)}")

        print("[4/8] override global phone -> enabled=false, full-scan should not match global phone")
        override = toggle_global_phone(client, token, rule_set_id, enabled=False)
        override_id = str(override["id"])
        after_disable = full_scan(client, token, rule_set_id, PHONE_TEXT)
        if GLOBAL_PHONE_KEY in stable_keys(after_disable):
            fail(
                "global phone key still matched after override disable\n"
                f"{pretty(after_disable)}"
            )

        print("[5/8] override global phone -> enabled=true, full-scan should match again")
        toggle_global_phone(client, token, rule_set_id, enabled=True)
        after_enable = full_scan(client, token, rule_set_id, PHONE_TEXT)
        if GLOBAL_PHONE_KEY not in stable_keys(after_enable):
            fail(
                "global phone key missing after override enable\n"
                f"{pretty(after_enable)}"
            )

        print("[6/8] create custom phone block, expect final_action=block")
        custom_rule = create_custom_phone_block(client, token, rule_set_id)
        custom_rule_id = str(custom_rule["id"])
        with_custom_block = full_scan(client, token, rule_set_id, PHONE_TEXT)
        if str(with_custom_block.get("final_action", "")).lower() != "block":
            fail(f"expected final_action=block\n{pretty(with_custom_block)}")

        print("[7/8] update custom action block -> mask, expect final_action=mask")
        patch_resp = patch_rule_action(
            client, token, rule_set_id, custom_rule_id, action="mask"
        )
        patch_body = expect_status(patch_resp, 200)
        ensure_ok_api(patch_body, "patch custom action mask")
        with_custom_mask = full_scan(client, token, rule_set_id, PHONE_TEXT)
        if str(with_custom_mask.get("final_action", "")).lower() != "mask":
            fail(f"expected final_action=mask\n{pretty(with_custom_mask)}")

        print("[8/8] patch override action should fail (422)")
        patch_override_resp = patch_rule_action(
            client, token, rule_set_id, override_id, action="block"
        )
        if patch_override_resp.status_code != 422:
            fail(
                f"expected 422 for override action update, got {patch_override_resp.status_code}\n"
                f"{patch_override_resp.text}"
            )

        print("ALL PASS: precedence + full-scan checks are good.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)





