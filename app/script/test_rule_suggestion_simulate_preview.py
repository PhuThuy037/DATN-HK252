from __future__ import annotations

import os
import time
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "30"))

ADMIN_EMAIL = os.getenv(
    "TEST_ADMIN_EMAIL", f"admin.suggest.simulate.{int(time.time())}@test.com"
).strip().lower()
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "123456")
ADMIN_NAME = os.getenv("TEST_ADMIN_NAME", "Admin Suggest Simulate")


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
        json={"name": f"Suggestion Simulate Co {int(time.time())}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"create rule set failed: HTTP {r.status_code}\n{r.text}")
    cid = str((r.json().get("data") or {}).get("id") or "")
    if not cid:
        fail("rule_set id missing")
    return cid


def generate_suggestion(
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
        fail(f"generate suggestion failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def edit_suggestion(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    suggestion_id: str,
    *,
    stable_key: str,
    name: str,
    conditions: dict[str, Any],
    action: str,
    expected_version: int,
    context_terms: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "expected_version": expected_version,
        "draft": {
            "rule": {
                "stable_key": stable_key,
                "name": name,
                "description": "simulate preview test",
                "scope": "prompt",
                "conditions": conditions,
                "action": action,
                "severity": "medium",
                "priority": 250,
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [],
        },
    }
    if context_terms is not None:
        payload["draft"]["context_terms"] = context_terms
    r = client.patch(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"edit suggestion failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def confirm_suggestion(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    suggestion_id: str,
    *,
    expected_version: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"reason": "confirm for simulate"}
    if expected_version is not None:
        payload["expected_version"] = expected_version
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/confirm",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"confirm suggestion failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def reject_suggestion(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    suggestion_id: str,
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/reject",
        json={"reason": "reject for simulate negative"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"reject suggestion failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def apply_suggestion(
    client: httpx.Client,
    token: str,
    rule_set_id: str,
    suggestion_id: str,
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/apply",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"apply suggestion failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def list_rules(client: httpx.Client, token: str, rule_set_id: str) -> list[dict[str, Any]]:
    r = client.get(
        f"{V1}/rule-sets/{rule_set_id}/rules",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        fail(f"list rules failed: HTTP {r.status_code}\n{r.text}")
    return list(r.json().get("data") or [])


def simulate(
    client: httpx.Client,
    token: str,
    suggestion_id: str,
    *,
    samples: list[str],
    include_examples: bool,
    expected_status: int = 200,
) -> tuple[int, dict[str, Any]]:
    return simulate_raw(
        client,
        token,
        suggestion_id,
        payload={"samples": samples, "include_examples": include_examples},
        expected_status=expected_status,
    )


def simulate_raw(
    client: httpx.Client,
    token: str,
    suggestion_id: str,
    *,
    payload: dict[str, Any],
    expected_status: int = 200,
) -> tuple[int, dict[str, Any]]:
    r = client.post(
        f"{V1}/rule-suggestions/{suggestion_id}/simulate",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != expected_status:
        fail(
            "simulate expected="
            f"{expected_status}, got={r.status_code}\n{r.text}"
        )
    return r.status_code, body


def assert_action_breakdown_shape(data: dict[str, Any], *, source: str) -> None:
    breakdown = data.get("action_breakdown")
    if not isinstance(breakdown, dict):
        fail(f"{source}: action_breakdown must be object, got={data}")

    for key in ["ALLOW", "MASK", "BLOCK"]:
        if key not in breakdown:
            fail(f"{source}: action_breakdown missing key={key}: {breakdown}")
        if not isinstance(breakdown.get(key), int):
            fail(f"{source}: action_breakdown[{key}] must be int: {breakdown}")

    sample_size = int(data.get("sample_size") or 0)
    total = int(breakdown["ALLOW"]) + int(breakdown["MASK"]) + int(breakdown["BLOCK"])
    if total != sample_size:
        fail(
            f"{source}: action breakdown sum mismatch sample_size "
            f"(sum={total}, sample_size={sample_size})"
        )


def assert_results_shape_and_counts(
    data: dict[str, Any],
    *,
    source: str,
    expected_contents: list[str],
) -> None:
    results = list(data.get("results") or [])
    if len(results) != len(expected_contents):
        fail(f"{source}: results size mismatch expected={len(expected_contents)} got={results}")

    matched_by_result = 0
    action_count = {"ALLOW": 0, "MASK": 0, "BLOCK": 0}
    for idx, item in enumerate(results):
        if not isinstance(item, dict):
            fail(f"{source}: result[{idx}] must be object: {item}")

        content = item.get("content")
        if content != expected_contents[idx]:
            fail(f"{source}: result[{idx}].content mismatch: {item}")

        matched = item.get("matched")
        if not isinstance(matched, bool):
            fail(f"{source}: result[{idx}].matched must be bool: {item}")
        if matched:
            matched_by_result += 1

        action = str(item.get("predicted_action") or "")
        if action not in {"ALLOW", "MASK", "BLOCK"}:
            fail(f"{source}: result[{idx}].predicted_action invalid: {item}")
        action_count[action] += 1

    if int(data.get("matched_count") or 0) != matched_by_result:
        fail(
            f"{source}: matched_count mismatch expected={matched_by_result} "
            f"got={data.get('matched_count')}"
        )

    breakdown = data.get("action_breakdown") or {}
    if (
        int(breakdown.get("ALLOW") or 0) != action_count["ALLOW"]
        or int(breakdown.get("MASK") or 0) != action_count["MASK"]
        or int(breakdown.get("BLOCK") or 0) != action_count["BLOCK"]
    ):
        fail(f"{source}: action_breakdown mismatch with results: {data}")


def main() -> None:
    with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
        print("[1/10] register/login + create rule set")
        register_if_needed(client)
        token = login(client)
        rule_set_id = create_rule_set(client, token)
        print(f"rule_set_id={rule_set_id}")

        print("[2/10] draft INTERNAL_CODE exact-token simulate (match + non-match) + no persist")
        draft_generated = generate_suggestion(
            client,
            token,
            rule_set_id,
            "Tao suggestion de simulate draft",
        )
        draft_suggestion_id = str(draft_generated.get("id") or "")
        if not draft_suggestion_id:
            fail(f"missing draft suggestion_id: {draft_generated}")

        draft_token = "zxq-thuydt123-1989"
        draft_stable_key = f"company.custom.simulate.draft.internal_code.{int(time.time())}"
        draft_edited = edit_suggestion(
            client,
            token,
            rule_set_id,
            draft_suggestion_id,
            stable_key=draft_stable_key,
            name="Simulate draft INTERNAL_CODE mask",
            conditions={
                "all": [
                    {
                        "signal": {
                            "field": "context_keywords",
                            "any_of": [draft_token],
                        }
                    }
                ]
            },
            action="mask",
            context_terms=[
                {
                    "entity_type": "INTERNAL_CODE",
                    "term": draft_token,
                    "lang": "vi",
                    "weight": 1,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                }
            ],
            expected_version=int(draft_generated.get("version") or 1),
        )
        if str(draft_edited.get("status") or "") != "draft":
            fail(f"edited suggestion should still be draft: {draft_edited}")

        before_rules = list_rules(client, token, rule_set_id)
        if any(str(r.get("stable_key") or "") == draft_stable_key for r in before_rules):
            fail("draft stable_key unexpectedly exists in rules before simulate")

        _, simulate_draft_body = simulate(
            client,
            token,
            draft_suggestion_id,
            samples=[
                "Toi co ma don zxq-thuydt123-1989, nho kiem tra",
                "Xin chao ban",
            ],
            include_examples=True,
            expected_status=200,
        )
        simulate_draft = simulate_draft_body.get("data") or {}
        if str(simulate_draft.get("suggestion_id") or "") != draft_suggestion_id:
            fail(f"simulate draft suggestion_id mismatch: {simulate_draft}")
        if int(simulate_draft.get("sample_size") or 0) != 2:
            fail(f"sample_size mismatch: {simulate_draft}")
        if not isinstance(simulate_draft.get("runtime_usable"), bool):
            fail(f"runtime_usable must be bool: {simulate_draft}")
        if not isinstance(simulate_draft.get("runtime_warnings"), list):
            fail(f"runtime_warnings must be list: {simulate_draft}")
        assert_action_breakdown_shape(simulate_draft, source="draft_simulate")
        assert_results_shape_and_counts(
            simulate_draft,
            source="draft_simulate",
            expected_contents=[
                "Toi co ma don zxq-thuydt123-1989, nho kiem tra",
                "Xin chao ban",
            ],
        )
        draft_results = list(simulate_draft.get("results") or [])
        if not bool((draft_results[0] if draft_results else {}).get("matched")):
            fail(f"first sample with exact token should match: {simulate_draft}")
        if str((draft_results[0] if draft_results else {}).get("predicted_action") or "") != "MASK":
            fail(f"first sample should predict MASK: {simulate_draft}")
        if bool((draft_results[1] if len(draft_results) > 1 else {}).get("matched")):
            fail(f"second sample should not match: {simulate_draft}")
        if str((draft_results[1] if len(draft_results) > 1 else {}).get("predicted_action") or "") != "ALLOW":
            fail(f"second sample should predict ALLOW: {simulate_draft}")

        _, simulate_draft_non_match_body = simulate(
            client,
            token,
            draft_suggestion_id,
            samples=[
                "Xin chao ban",
                "Toi dang hoi lich hop tuan nay",
            ],
            include_examples=True,
            expected_status=200,
        )
        simulate_draft_non_match = simulate_draft_non_match_body.get("data") or {}
        assert_action_breakdown_shape(simulate_draft_non_match, source="draft_simulate_non_match")
        assert_results_shape_and_counts(
            simulate_draft_non_match,
            source="draft_simulate_non_match",
            expected_contents=[
                "Xin chao ban",
                "Toi dang hoi lich hop tuan nay",
            ],
        )
        if int(simulate_draft_non_match.get("matched_count") or 0) != 0:
            fail(f"non-match samples should have matched_count=0: {simulate_draft_non_match}")
        for item in list(simulate_draft_non_match.get("results") or []):
            if bool(item.get("matched")):
                fail(f"non-match sample matched unexpectedly: {simulate_draft_non_match}")
            if str(item.get("predicted_action") or "") != "ALLOW":
                fail(f"non-match sample should predict ALLOW: {simulate_draft_non_match}")

        after_rules = list_rules(client, token, rule_set_id)
        if any(str(r.get("stable_key") or "") == draft_stable_key for r in after_rules):
            fail("simulate must not persist draft rule into rules table")

        print("[3/10] simulate validation errors for invalid samples payload")
        _, simulate_invalid_body = simulate(
            client,
            token,
            draft_suggestion_id,
            samples=[],
            include_examples=True,
            expected_status=422,
        )
        if str((((simulate_invalid_body.get("error") or {}).get("code")) or "")) != "VALIDATION_ERROR":
            fail(f"simulate empty samples should be VALIDATION_ERROR: {simulate_invalid_body}")

        _, simulate_missing_body = simulate_raw(
            client,
            token,
            draft_suggestion_id,
            payload={"include_examples": True},
            expected_status=422,
        )
        if str((((simulate_missing_body.get("error") or {}).get("code")) or "")) != "VALIDATION_ERROR":
            fail(f"simulate missing samples should be VALIDATION_ERROR: {simulate_missing_body}")

        too_long_sample = "x" * 2001
        _, simulate_too_long_body = simulate(
            client,
            token,
            draft_suggestion_id,
            samples=[too_long_sample],
            include_examples=True,
            expected_status=422,
        )
        if str((((simulate_too_long_body.get("error") or {}).get("code")) or "")) != "VALIDATION_ERROR":
            fail(f"simulate too long sample should be VALIDATION_ERROR: {simulate_too_long_body}")

        too_many_samples = [f"sample-{i}" for i in range(101)]
        _, simulate_too_many_body = simulate(
            client,
            token,
            draft_suggestion_id,
            samples=too_many_samples,
            include_examples=True,
            expected_status=422,
        )
        if str((((simulate_too_many_body.get("error") or {}).get("code")) or "")) != "VALIDATION_ERROR":
            fail(f"simulate too many samples should be VALIDATION_ERROR: {simulate_too_many_body}")

        print("[4/10] approved suggestion simulate success with mixed samples")
        approved_generated = generate_suggestion(
            client,
            token,
            rule_set_id,
            "Tao suggestion de simulate approved",
        )
        approved_suggestion_id = str(approved_generated.get("id") or "")
        if not approved_suggestion_id:
            fail(f"missing approved suggestion_id: {approved_generated}")

        approved_stable_key = f"company.custom.simulate.approved.unique.{int(time.time())}"
        approved_edited = edit_suggestion(
            client,
            token,
            rule_set_id,
            approved_suggestion_id,
            stable_key=approved_stable_key,
            name="Simulate approved unique policy",
            conditions={
                "all": [
                    {"signal": {"field": "persona", "equals": "office"}},
                    {"signal": {"field": "context_keywords", "any_of": ["simulate_unique_kw"]}},
                ]
            },
            action="mask",
            expected_version=int(approved_generated.get("version") or 1),
        )
        approved_confirmed = confirm_suggestion(
            client,
            token,
            rule_set_id,
            approved_suggestion_id,
            expected_version=int(approved_edited.get("version") or 1),
        )
        if str(approved_confirmed.get("status") or "") != "approved":
            fail(f"suggestion should be approved: {approved_confirmed}")

        _, simulate_approved_body = simulate(
            client,
            token,
            approved_suggestion_id,
            samples=[
                "Phong office can chia se simulate_unique_kw cho bao cao",
                "No sensitive data here",
            ],
            include_examples=False,
            expected_status=200,
        )
        simulate_approved = simulate_approved_body.get("data") or {}
        assert_action_breakdown_shape(simulate_approved, source="approved_simulate")
        assert_results_shape_and_counts(
            simulate_approved,
            source="approved_simulate",
            expected_contents=[
                "Phong office can chia se simulate_unique_kw cho bao cao",
                "No sensitive data here",
            ],
        )
        approved_results = list(simulate_approved.get("results") or [])
        if not bool((approved_results[0] if approved_results else {}).get("matched")):
            fail(f"first approved sample should match: {simulate_approved}")
        if bool((approved_results[1] if len(approved_results) > 1 else {}).get("matched")):
            fail(f"second approved sample should not match: {simulate_approved}")

        print("[5/10] applied suggestion should be rejected for simulate")
        applied = apply_suggestion(client, token, rule_set_id, approved_suggestion_id)
        if not str(applied.get("rule_id") or ""):
            fail(f"apply should return rule_id: {applied}")

        _, simulate_applied_body = simulate(
            client,
            token,
            approved_suggestion_id,
            samples=["test applied status"],
            include_examples=True,
            expected_status=422,
        )
        if str((((simulate_applied_body.get("error") or {}).get("code")) or "")) != "VALIDATION_ERROR":
            fail(f"applied simulate should be VALIDATION_ERROR: {simulate_applied_body}")

        print("[6/10] rejected suggestion should be rejected for simulate")
        rejected_generated = generate_suggestion(
            client,
            token,
            rule_set_id,
            "Tao suggestion de reject truoc khi simulate",
        )
        rejected_suggestion_id = str(rejected_generated.get("id") or "")
        if not rejected_suggestion_id:
            fail(f"missing rejected suggestion_id: {rejected_generated}")
        rejected = reject_suggestion(client, token, rule_set_id, rejected_suggestion_id)
        if str(rejected.get("status") or "") != "rejected":
            fail(f"suggestion should be rejected: {rejected}")

        _, simulate_rejected_body = simulate(
            client,
            token,
            rejected_suggestion_id,
            samples=["test rejected status"],
            include_examples=True,
            expected_status=422,
        )
        if str((((simulate_rejected_body.get("error") or {}).get("code")) or "")) != "VALIDATION_ERROR":
            fail(f"rejected simulate should be VALIDATION_ERROR: {simulate_rejected_body}")

    print("ALL PASS: simulate/dry-run/preview impact feature works as expected.")


if __name__ == "__main__":
    main()
