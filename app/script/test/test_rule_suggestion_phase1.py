from __future__ import annotations

import os
import time
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "30"))

ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "admin.suggest@test.com").strip().lower()
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "123456")
ADMIN_NAME = os.getenv("TEST_ADMIN_NAME", "Admin Suggest")


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
    body = r.json()
    token = (((body.get("data") or {}).get("access_token")) or "").strip()
    if not token:
        fail("login did not return access token")
    return token


def create_rule_set(client: httpx.Client, token: str) -> str:
    r = client.post(
        f"{V1}/rule-sets",
        json={"name": f"Suggestion Co {int(time.time())}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"create rule set failed: HTTP {r.status_code}\n{r.text}")
    rule_set_id = str((r.json().get("data") or {}).get("id") or "")
    if not rule_set_id:
        fail("create rule set did not return id")
    return rule_set_id


def generate(client: httpx.Client, token: str, rule_set_id: str, prompt: str) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/generate",
        json={"prompt": prompt},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"generate failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def get_suggestion(
    client: httpx.Client, token: str, rule_set_id: str, suggestion_id: str
) -> dict[str, Any]:
    r = client.get(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"get suggestion failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def assert_feature1_fields(payload: dict[str, Any], *, source: str) -> None:
    explanation = payload.get("explanation")
    if not isinstance(explanation, dict):
        fail(f"{source}: missing explanation object: {payload}")
    for key in ["summary", "detected_intent", "derived_terms", "action_reason"]:
        if key not in explanation:
            fail(f"{source}: explanation missing key={key}: {explanation}")
    if not isinstance(explanation.get("derived_terms"), list):
        fail(f"{source}: explanation.derived_terms should be list: {explanation}")

    quality = payload.get("quality_signals")
    if not isinstance(quality, dict):
        fail(f"{source}: missing quality_signals object: {payload}")
    for key in [
        "intent_confidence",
        "duplicate_risk",
        "conflict_risk",
        "generation_source",
        "has_policy_context",
    ]:
        if key not in quality:
            fail(f"{source}: quality_signals missing key={key}: {quality}")

    confidence = float(quality.get("intent_confidence") or 0.0)
    if confidence < 0.0 or confidence > 1.0:
        fail(f"{source}: intent_confidence out of range [0,1]: {quality}")
    if str(quality.get("conflict_risk") or "") != "unknown":
        fail(f"{source}: conflict_risk should be 'unknown' in phase 1: {quality}")
    if bool(quality.get("has_policy_context")) is not False:
        fail(f"{source}: has_policy_context should be false in phase 1: {quality}")


def patch_edit(
    client: httpx.Client, token: str, rule_set_id: str, suggestion_id: str, draft: dict[str, Any], expected_version: int
) -> dict[str, Any]:
    r = client.patch(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}",
        json={"draft": draft, "expected_version": expected_version},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"edit failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def confirm(
    client: httpx.Client, token: str, rule_set_id: str, suggestion_id: str
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/confirm",
        json={"reason": "looks good"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"confirm failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def apply(
    client: httpx.Client, token: str, rule_set_id: str, suggestion_id: str
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/apply",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"apply failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def list_rules(client: httpx.Client, token: str, rule_set_id: str) -> list[dict[str, Any]]:
    r = client.get(
        f"{V1}/rule-sets/{rule_set_id}/rules",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"list rules failed: HTTP {r.status_code}\n{r.text}")
    return list(r.json().get("data") or [])


def list_logs(
    client: httpx.Client, token: str, rule_set_id: str, suggestion_id: str
) -> list[dict[str, Any]]:
    r = client.get(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"list logs failed: HTTP {r.status_code}\n{r.text}")
    return list(r.json().get("data") or [])


def main() -> None:
    with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
        print("[1/8] register/login admin")
        register_if_needed(client)
        token = login(client)

        print("[2/8] create rule set")
        rule_set_id = create_rule_set(client, token)
        print(f"rule_set_id={rule_set_id}")

        prompt = "Hay tao rule chan so dien thoai va bo sung context hotline"
        print("[3/8] generate suggestion")
        s1 = generate(client, token, rule_set_id, prompt)
        suggestion_id = str(s1.get("id") or "")
        if not suggestion_id:
            fail(f"generate did not return suggestion id: {s1}")
        if s1.get("status") != "draft":
            fail(f"suggestion should be draft: {s1}")
        assert_feature1_fields(s1, source="generate")

        print("[3.1/8] get suggestion should include explanation + quality_signals")
        got = get_suggestion(client, token, rule_set_id, suggestion_id)
        if str(got.get("id") or "") != suggestion_id:
            fail(f"get returned mismatched suggestion id: {got}")
        assert_feature1_fields(got, source="get")

        print("[4/8] generate same prompt should dedupe to same suggestion")
        s2 = generate(client, token, rule_set_id, prompt)
        if str(s2.get("id") or "") != suggestion_id:
            fail(f"dedupe failed: first={suggestion_id}, second={s2.get('id')}")
        assert_feature1_fields(s2, source="generate_dedupe")

        print("[5/8] edit draft")
        draft = dict(s1.get("draft") or {})
        draft_rule = dict(draft.get("rule") or {})
        draft_rule["name"] = f"{draft_rule.get('name', 'Suggested Rule')} v2"
        draft["rule"] = draft_rule
        edited = patch_edit(
            client,
            token,
            rule_set_id,
            suggestion_id,
            draft,
            expected_version=int(s1.get("version") or 1),
        )
        if edited.get("version") != 2:
            fail(f"expected version=2 after edit, got {edited.get('version')}")

        print("[6/8] confirm")
        confirmed = confirm(client, token, rule_set_id, suggestion_id)
        if confirmed.get("status") != "approved":
            fail(f"confirm should set approved: {confirmed}")

        print("[7/8] apply")
        applied = apply(client, token, rule_set_id, suggestion_id)
        rule_id = str(applied.get("rule_id") or "")
        if not rule_id:
            fail(f"apply should return rule_id: {applied}")

        print("[8/8] verify applied rule exists + logs captured")
        rules = list_rules(client, token, rule_set_id)
        stable_key = (((confirmed.get("draft") or {}).get("rule") or {}).get("stable_key")) or ""
        if not any(str(r.get("stable_key") or "") == stable_key for r in rules):
            fail(f"applied stable_key not found in rule-set rules: {stable_key}")
        logs = list_logs(client, token, rule_set_id, suggestion_id)
        if len(logs) < 3:
            fail(f"expected >=3 logs (create/edit/confirm/apply), got {len(logs)}")

    print("ALL PASS: suggestion phase 4.3 batch-1 happy path is working.")


if __name__ == "__main__":
    main()



