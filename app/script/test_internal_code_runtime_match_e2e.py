from __future__ import annotations

import os
import time
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "30"))
PWD = os.getenv("TEST_USER_PASSWORD", "123456")
GLOBAL_PHONE_KEY = "global.pii.phone.mask"


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
    email = f"internal.code.e2e.{now}@test.com"
    name = f"Internal Code E2E {now}"

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
        json={"name": f"Internal Code Runtime Match {int(time.time())}"},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"create rule set failed: HTTP {r.status_code}\n{r.text}")
    rule_set_id = str((r.json().get("data") or {}).get("id") or "").strip()
    if not rule_set_id:
        fail("missing rule_set_id")
    return rule_set_id


def generate_custom_secret_suggestion(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    token_term: str,
) -> dict[str, Any]:
    prompt = f"Tao rule mask ma noi bo {token_term}"
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/generate",
        json={"prompt": prompt},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"generate suggestion failed: HTTP {r.status_code}\n{r.text}")
    out = r.json().get("data") or {}
    if str(out.get("status") or "") != "draft":
        fail(f"suggestion should be draft: {out}")
    return out


def confirm_suggestion(client: httpx.Client, token: str, rule_set_id: str, suggestion_id: str) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/confirm",
        json={"reason": "e2e confirm"},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"confirm suggestion failed: HTTP {r.status_code}\n{r.text}")
    out = r.json().get("data") or {}
    if str(out.get("status") or "") != "approved":
        fail(f"suggestion should be approved: {out}")
    return out


def apply_suggestion(client: httpx.Client, token: str, rule_set_id: str, suggestion_id: str) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/apply",
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"apply suggestion failed: HTTP {r.status_code}\n{r.text}")
    out = r.json().get("data") or {}
    if not str(out.get("rule_id") or "").strip():
        fail(f"apply must return rule_id: {out}")
    return out


def create_rule_set_conversation(client: httpx.Client, token: str, rule_set_id: str) -> str:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/conversations",
        json={"title": f"Internal code test {int(time.time())}"},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"create conversation failed: HTTP {r.status_code}\n{r.text}")
    data = r.json().get("data") or {}
    conv_id = str(data.get("id") or "").strip()
    if not conv_id:
        fail(f"missing conversation id: {data}")
    if str(data.get("rule_set_id") or "") != rule_set_id:
        fail(f"conversation rule_set mismatch: expected={rule_set_id}, got={data}")
    return conv_id


def send_message(
    client: httpx.Client,
    token: str,
    conversation_id: str,
    content: str,
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/conversations/{conversation_id}/messages",
        json={"content": content, "input_type": "user_input"},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"send message failed: HTTP {r.status_code}\n{r.text}")
    return r.json()


def list_rules(client: httpx.Client, token: str, rule_set_id: str) -> list[dict[str, Any]]:
    r = client.get(
        f"{V1}/rule-sets/{rule_set_id}/rules",
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"list rules failed: HTTP {r.status_code}\n{r.text}")
    rows = r.json().get("data") or []
    if not isinstance(rows, list):
        fail(f"list rules returned non-list: {rows}")
    return rows


def find_rule_id_by_stable_key(rows: list[dict[str, Any]], stable_key: str) -> str:
    for row in rows:
        if str(row.get("stable_key") or "") == stable_key:
            rid = str(row.get("id") or "").strip()
            if rid:
                return rid
    return ""


def main() -> None:
    with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
        print("[1/9] register/login fresh user")
        token = register_and_login_fresh_user(client)

        print("[2/9] create rule-set")
        rule_set_id = create_rule_set(client, token)
        print(f"rule_set_id={rule_set_id}")

        token_term = f"ZXQ-UNSEEN-{int(time.time())}"
        print("[3/9] generate custom-secret suggestion")
        generated = generate_custom_secret_suggestion(client, token, rule_set_id, token_term)
        suggestion_id = str(generated.get("id") or "").strip()
        if not suggestion_id:
            fail(f"missing suggestion_id: {generated}")

        draft_rule = ((generated.get("draft") or {}).get("rule") or {})
        expected_action = str(draft_rule.get("action") or "").strip().lower()
        if expected_action not in {"mask", "block"}:
            fail(f"custom-secret expected action should be mask/block, got={expected_action}, draft={draft_rule}")

        print("[4/9] confirm + apply suggestion")
        confirm_suggestion(client, token, rule_set_id, suggestion_id)
        applied = apply_suggestion(client, token, rule_set_id, suggestion_id)
        applied_rule_id = str(applied.get("rule_id") or "").strip()

        print("[5/9] create conversation under same rule-set")
        conversation_id = create_rule_set_conversation(client, token, rule_set_id)

        print("[6/9] send exact-token message; runtime must match applied rule")
        pos_payload = send_message(
            client,
            token,
            conversation_id,
            f"Toi co ma don hang {token_term.lower()}",
        )
        pos_data = pos_payload.get("data") or {}
        pos_action = str(pos_data.get("final_action") or "").strip().lower()
        if pos_action == "allow":
            fail(f"final_action should not be allow for matched internal code rule: {pos_payload}")

        matched_ids = [str(x) for x in (pos_data.get("matched_rule_ids") or []) if str(x)]
        if not matched_ids:
            fail(f"matched_rule_ids must not be empty for token-positive case: {pos_payload}")
        if applied_rule_id not in matched_ids:
            fail(f"applied rule_id not found in matched_rule_ids: applied={applied_rule_id}, got={matched_ids}")

        signals = (((pos_data.get("entities_json") or {}).get("signals")) or {})
        kws = [str(x).strip().lower() for x in (signals.get("context_keywords") or []) if str(x).strip()]
        if token_term.lower() not in kws:
            fail(f"context_keywords should include exact token term: token={token_term.lower()}, kws={kws}")

        print("[7/9] send no-token message; custom internal-code rule must not over-match")
        neg_payload = send_message(
            client,
            token,
            conversation_id,
            "Hom nay team hop sprint planning, khong co ma noi bo",
        )
        neg_data = neg_payload.get("data") or {}
        neg_matched_ids = [str(x) for x in (neg_data.get("matched_rule_ids") or []) if str(x)]
        if applied_rule_id in neg_matched_ids:
            fail(f"custom internal-code rule matched bừa on no-token message: {neg_payload}")

        print("[8/9] non-INTERNAL_CODE old rule path should still work (global phone)")
        rows = list_rules(client, token, rule_set_id)
        global_phone_rule_id = find_rule_id_by_stable_key(rows, GLOBAL_PHONE_KEY)
        if not global_phone_rule_id:
            fail(f"missing expected global rule stable_key={GLOBAL_PHONE_KEY}")

        pii_payload = send_message(
            client,
            token,
            conversation_id,
            "So dien thoai lien he cua toi la 0901234567",
        )
        pii_data = pii_payload.get("data") or {}
        pii_matched_ids = [str(x) for x in (pii_data.get("matched_rule_ids") or []) if str(x)]
        if global_phone_rule_id not in pii_matched_ids:
            fail(f"global phone rule should still match after INTERNAL_CODE fix: {pii_payload}")
        if applied_rule_id in pii_matched_ids:
            fail(f"internal-code rule should not match phone-only message: {pii_payload}")

        print("[9/9] final action sanity for positive/negative paths")
        if expected_action in {"mask", "block"} and pos_action == "allow":
            fail(f"positive case action should not be allow, got={pos_action}")
        # no-token case should not be forced by custom internal-code rule.
        # It can still be allow/mask/block by other independent rules.

    print("ALL PASS: INTERNAL_CODE suggestion/apply/runtime match contract works end-to-end.")


if __name__ == "__main__":
    main()
