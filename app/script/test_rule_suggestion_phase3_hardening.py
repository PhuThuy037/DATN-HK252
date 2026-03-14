from __future__ import annotations

import os
import time
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "30"))

ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "admin.suggest.hardening@test.com").strip().lower()
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "123456")
ADMIN_NAME = os.getenv("TEST_ADMIN_NAME", "Admin Suggest Hardening")


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
        json={"name": f"Suggestion Hardening Co {int(time.time())}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"create rule set failed: HTTP {r.status_code}\n{r.text}")
    cid = str((r.json().get("data") or {}).get("id") or "")
    if not cid:
        fail("rule_set id missing")
    return cid


def generate(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    prompt: str,
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/generate",
        json={"prompt": prompt},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"generate failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def get_logs(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    suggestion_id: str,
) -> list[dict[str, Any]]:
    r = client.get(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"get logs failed: HTTP {r.status_code}\n{r.text}")
    return list(r.json().get("data") or [])


def patch_edit(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    suggestion_id: str,
    draft: dict[str, Any],
    expected_version: int,
    expected_status: int = 200,
) -> tuple[int, dict[str, Any]]:
    r = client.patch(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}",
        json={"draft": draft, "expected_version": expected_version},
        headers={"Authorization": f"Bearer {token}"},
    )
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != expected_status:
        fail(f"edit expected={expected_status}, got={r.status_code}\n{r.text}")
    return r.status_code, body


def confirm(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    suggestion_id: str,
    expected_version: int,
    expected_status: int = 200,
) -> tuple[int, dict[str, Any]]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/confirm",
        json={"reason": "phase3_confirm", "expected_version": expected_version},
        headers={"Authorization": f"Bearer {token}"},
    )
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != expected_status:
        fail(f"confirm expected={expected_status}, got={r.status_code}\n{r.text}")
    return r.status_code, body


def reject(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    suggestion_id: str,
    expected_version: int,
    expected_status: int,
) -> tuple[int, dict[str, Any]]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/reject",
        json={"reason": "phase3_reject", "expected_version": expected_version},
        headers={"Authorization": f"Bearer {token}"},
    )
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != expected_status:
        fail(f"reject expected={expected_status}, got={r.status_code}\n{r.text}")
    return r.status_code, body


def apply_suggestion(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    suggestion_id: str,
    expected_version: int | None,
    expected_status: int = 200,
) -> tuple[int, dict[str, Any]]:
    payload = {"expected_version": expected_version} if expected_version is not None else None
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/apply",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != expected_status:
        fail(f"apply expected={expected_status}, got={r.status_code}\n{r.text}")
    return r.status_code, body


def full_scan(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    text: str,
) -> dict[str, Any]:
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
        print("[1/10] register/login + create rule set")
        register_if_needed(client)
        token = login(client)
        rule_set_id = create_rule_set(client, token)
        print(f"rule_set_id={rule_set_id}")

        print("[2/10] duplicate generate should return same suggestion id")
        dup_prompt = "Tao rule block API secret noi bo cho dev"
        dup_1 = generate(client, token, rule_set_id, dup_prompt)
        dup_2 = generate(client, token, rule_set_id, dup_prompt)
        dup_id_1 = str(dup_1.get("id") or "")
        dup_id_2 = str(dup_2.get("id") or "")
        if dup_id_1 != dup_id_2:
            fail(f"duplicate generate should reuse id, got {dup_id_1} vs {dup_id_2}")

        print("[3/10] duplicate-hit action should be logged")
        dup_logs = get_logs(client, token, rule_set_id, dup_id_1)
        if not any(str(x.get("action") or "") == "suggestion.generate.duplicate_hit" for x in dup_logs):
            fail(f"duplicate_hit log not found: {dup_logs}")

        print("[4/10] generate editable suggestion")
        base = generate(client, token, rule_set_id, "Tao rule mask thong tin lien he")
        suggestion_id = str(base.get("id") or "")
        version_1 = int(base.get("version") or 1)
        if not suggestion_id:
            fail(f"missing suggestion_id: {base}")

        print("[5/10] stale edit version should fail (409)")
        _, stale_edit_body = patch_edit(
            client,
            token,
            rule_set_id,
            suggestion_id,
            draft=base.get("draft") or {},
            expected_version=version_1 + 99,
            expected_status=409,
        )
        if str((((stale_edit_body.get("error") or {}).get("code")) or "")) != "CONFLICT":
            fail(f"expected CONFLICT on stale edit, got {stale_edit_body}")

        print("[6/10] edit success with entity_type split normalization")
        draft = dict(base.get("draft") or {})
        rule = dict(draft.get("rule") or {})
        rule["stable_key"] = f"personal.custom.phase3.multi.entity.{int(time.time())}"
        rule["name"] = "Phase3 multi-entity block"
        rule["conditions"] = {"any": [{"entity_type": "EMAIL|PHONE"}]}
        rule["action"] = "block"
        rule["priority"] = 500
        draft["rule"] = rule
        draft["context_terms"] = [
            {
                "entity_type": "EMAIL|PHONE",
                "term": "lien he",
                "lang": "vi",
                "weight": 1.0,
                "window_1": 60,
                "window_2": 20,
                "enabled": True,
            }
        ]
        _, edit_body = patch_edit(
            client,
            token,
            rule_set_id,
            suggestion_id,
            draft=draft,
            expected_version=version_1,
            expected_status=200,
        )
        edited = edit_body.get("data") or {}
        version_2 = int(edited.get("version") or 0)
        if version_2 != version_1 + 1:
            fail(f"version should increase after edit, got {version_2}")
        normalized_conditions = (((edited.get("draft") or {}).get("rule") or {}).get("conditions")) or {}
        leaves = ((normalized_conditions.get("any") or []))
        entity_values = sorted(str(x.get("entity_type") or "") for x in leaves if isinstance(x, dict))
        if entity_values != ["EMAIL", "PHONE"]:
            fail(f"entity_type split normalization failed: {normalized_conditions}")
        normalized_terms = list(((edited.get("draft") or {}).get("context_terms")) or [])
        term_entities = sorted(str(x.get("entity_type") or "") for x in normalized_terms)
        if term_entities != ["EMAIL", "PHONE"]:
            fail(f"context term split normalization failed: {normalized_terms}")

        print("[7/10] stale confirm should fail, correct confirm should pass")
        _, stale_confirm_body = confirm(
            client,
            token,
            rule_set_id,
            suggestion_id,
            expected_version=version_2 - 1,
            expected_status=409,
        )
        if str((((stale_confirm_body.get("error") or {}).get("code")) or "")) != "CONFLICT":
            fail(f"expected CONFLICT on stale confirm, got {stale_confirm_body}")

        _, confirm_body = confirm(
            client,
            token,
            rule_set_id,
            suggestion_id,
            expected_version=version_2,
            expected_status=200,
        )
        confirmed = confirm_body.get("data") or {}
        version_3 = int(confirmed.get("version") or 0)
        if str(confirmed.get("status") or "") != "approved":
            fail(f"suggestion should be approved: {confirmed}")
        if version_3 != version_2 + 1:
            fail(f"version should increase after confirm, got {version_3}")

        print("[8/10] stale apply should fail, correct apply should pass, second apply idempotent")
        _, stale_apply_body = apply_suggestion(
            client,
            token,
            rule_set_id,
            suggestion_id,
            expected_version=version_3 - 1,
            expected_status=409,
        )
        if str((((stale_apply_body.get("error") or {}).get("code")) or "")) != "CONFLICT":
            fail(f"expected CONFLICT on stale apply, got {stale_apply_body}")

        _, apply_body = apply_suggestion(
            client,
            token,
            rule_set_id,
            suggestion_id,
            expected_version=version_3,
            expected_status=200,
        )
        applied = apply_body.get("data") or {}
        rule_id = str(applied.get("rule_id") or "")
        if not rule_id:
            fail(f"apply missing rule_id: {applied}")

        _, apply_again_body = apply_suggestion(
            client,
            token,
            rule_set_id,
            suggestion_id,
            expected_version=None,
            expected_status=200,
        )
        applied_again = apply_again_body.get("data") or {}
        if str(applied_again.get("rule_id") or "") != rule_id:
            fail(f"idempotent apply should return same rule_id: {apply_again_body}")

        print("[9/10] reject after applied should fail")
        _, reject_body = reject(
            client,
            token,
            rule_set_id,
            suggestion_id,
            expected_version=version_3 + 1,
            expected_status=422,
        )
        if str((((reject_body.get("error") or {}).get("code")) or "")) != "VALIDATION_ERROR":
            fail(f"reject-after-applied should be VALIDATION_ERROR: {reject_body}")

        print("[10/10] full-scan should match applied rule")
        scan = full_scan(client, token, rule_set_id, "Lien he hotline 0901234567 de duoc ho tro")
        matched = list(scan.get("matched_rules") or [])
        if not any(str(x.get("rule_id") or "") == rule_id for x in matched):
            fail(f"full-scan did not match applied rule_id={rule_id}: {scan}")
        if str(scan.get("final_action") or "") != "block":
            fail(f"expected final_action=block from applied rule, got={scan}")

    print("ALL PASS: phase 4.3 batch-3 hardening scenarios are good.")


if __name__ == "__main__":
    main()





