from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


BASE = "http://localhost:8000/v1"
PWD = "123456"


def request_json(method: str, path: str, data: dict | None = None, token: str | None = None):
    body = None
    headers = {"Content-Type": "application/json", "accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(
        url=f"{BASE}{path}",
        method=method,
        headers=headers,
        data=body,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        parsed = json.loads(raw) if raw else {}
        return e.code, parsed


def register(email: str, name: str) -> None:
    code, _ = request_json(
        "POST",
        "/auth/register",
        {"email": email, "password": PWD, "name": name},
    )
    assert code in (200, 409), ("register", code)


def login(email: str) -> str:
    code, body = request_json("POST", "/auth/login", {"email": email, "password": PWD})
    assert code == 200, ("login", code, body)
    token = ((body.get("data") or {}).get("access_token") or "").strip()
    assert token, "missing access_token"
    return token


def main() -> None:
    now = int(time.time())
    owner_email = f"owner.smoke.{now}@test.com"
    other_email = f"other.smoke.{now}@test.com"

    register(owner_email, "Owner Smoke")
    register(other_email, "Other Smoke")

    owner_token = login(owner_email)
    other_token = login(other_email)

    # old/removed endpoints
    code, _ = request_json("GET", "/companies/me", token=owner_token)
    assert code == 404, ("companies_removed", code)

    code, _ = request_json("GET", "/rules/personal", token=owner_token)
    assert code == 404, ("personal_rules_removed", code)

    # create rule-set
    code, body = request_json("POST", "/rule-sets", {"name": "Demo Rule Set"}, owner_token)
    assert code == 200, ("create_rule_set", code, body)
    first_id = ((body.get("data") or {}).get("id") or "").strip()
    assert first_id, "missing rule_set id"

    # create again must fail clearly (no silent reuse)
    code, body = request_json(
        "POST", "/rule-sets", {"name": "Demo Rule Set 2"}, owner_token
    )
    assert code == 409, ("create_rule_set_again", code, body)
    err = body.get("error") or {}
    assert err.get("code") == "RULE_SET_ALREADY_EXISTS", ("error_code", err)

    # list mine
    code, body = request_json("GET", "/rule-sets/me", token=owner_token)
    assert code == 200, ("list_mine", code, body)
    items = (body.get("data") or [])
    assert isinstance(items, list) and len(items) <= 1, ("single_user_list", items)

    # owner can list rules
    code, _ = request_json("GET", f"/rule-sets/{first_id}/rules", token=owner_token)
    assert code == 200, ("owner_rules", code)

    # create a custom rule and verify contract field names
    code, created_rule_body = request_json(
        "POST",
        f"/rule-sets/{first_id}/rules",
        {
            "stable_key": f"rule_set.smoke.{now}",
            "name": "Smoke Rule",
            "conditions": {"entity_type": "PHONE"},
            "action": "mask",
            "severity": "medium",
            "priority": 1,
            "rag_mode": "off",
            "enabled": True,
        },
        owner_token,
    )
    assert code == 200, ("create_rule", code, created_rule_body)
    created_rule = created_rule_body.get("data") or {}
    assert created_rule.get("rule_set_id") == first_id, ("rule_rule_set_id", created_rule)
    assert "company_id" not in created_rule, ("rule_no_company_id", created_rule)
    assert created_rule.get("match_mode") == "strict_keyword", (
        "rule_default_match_mode",
        created_rule,
    )

    created_rule_id = str(created_rule.get("id") or "").strip()
    assert created_rule_id, ("missing_rule_id", created_rule)

    code, detail_body = request_json("GET", f"/rules/{created_rule_id}", token=owner_token)
    assert code == 200, ("rule_detail", code, detail_body)
    detail = detail_body.get("data") or {}
    assert detail.get("match_mode") == "strict_keyword", ("detail_match_mode", detail)

    code, explicit_rule_body = request_json(
        "POST",
        f"/rule-sets/{first_id}/rules",
        {
            "stable_key": f"rule_set.smoke.semantic.{now}",
            "name": "Semantic-ready Rule",
            "conditions": {"entity_type": "EMAIL"},
            "action": "mask",
            "severity": "medium",
            "priority": 2,
            "match_mode": "keyword_plus_semantic",
            "rag_mode": "off",
            "enabled": True,
        },
        owner_token,
    )
    assert code == 200, ("create_rule_explicit_match_mode", code, explicit_rule_body)
    explicit_rule = explicit_rule_body.get("data") or {}
    assert explicit_rule.get("match_mode") == "keyword_plus_semantic", (
        "explicit_match_mode",
        explicit_rule,
    )

    code, updated_rule_body = request_json(
        "PATCH",
        f"/rule-sets/{first_id}/rules/{created_rule_id}",
        {"match_mode": "keyword_plus_semantic"},
        owner_token,
    )
    assert code == 200, ("update_rule_match_mode", code, updated_rule_body)
    updated_rule = updated_rule_body.get("data") or {}
    assert updated_rule.get("match_mode") == "keyword_plus_semantic", (
        "updated_match_mode",
        updated_rule,
    )

    code, listed_rules_body = request_json(
        "GET",
        f"/rule-sets/{first_id}/rules",
        token=owner_token,
    )
    assert code == 200, ("list_rules_after_match_mode_update", code, listed_rules_body)
    listed_rules = listed_rules_body.get("data") or []
    listed_row = next(
        (row for row in listed_rules if str(row.get("id") or "") == created_rule_id),
        None,
    )
    assert listed_row is not None, ("listed_rule_exists", listed_rules)
    assert listed_row.get("match_mode") == "keyword_plus_semantic", (
        "listed_match_mode",
        listed_row,
    )
    explicit_listed_row = next(
        (row for row in listed_rules if str(row.get("id") or "") == str(explicit_rule.get("id") or "")),
        None,
    )
    assert explicit_listed_row is not None, ("listed_explicit_rule_exists", listed_rules)
    assert explicit_listed_row.get("match_mode") == "keyword_plus_semantic", (
        "listed_explicit_match_mode",
        explicit_listed_row,
    )

    # other user forbidden
    code, _ = request_json("GET", f"/rule-sets/{first_id}/rules", token=other_token)
    assert code == 403, ("other_forbidden", code)

    # create rule-set conversation should work for owner
    code, conv_body = request_json(
        "POST",
        f"/rule-sets/{first_id}/conversations",
        {"title": "smoke conversation"},
        owner_token,
    )
    assert code == 200, ("create_rule_set_conversation", code, conv_body)
    conv_data = conv_body.get("data") or {}
    assert conv_data.get("rule_set_id") == first_id, ("conversation_rule_set_id", conv_data)
    assert "company_id" not in conv_data, ("conversation_no_company_id", conv_data)

    # rule suggestions and policy routes (new)
    code, _ = request_json("GET", f"/rule-sets/{first_id}/rule-suggestions", token=owner_token)
    assert code == 200, ("rule_suggestions_list", code)

    code, _ = request_json("GET", f"/rule-sets/{first_id}/policy-documents", token=owner_token)
    assert code == 200, ("policy_documents_list", code)

    # create policy ingest job and verify contract field names
    code, job_body = request_json(
        "POST",
        f"/rule-sets/{first_id}/policy-ingest-jobs",
        {
            "items": [
                {
                    "stable_key": f"policy.smoke.{now}",
                    "title": "Smoke Policy",
                    "content": "Mask phone numbers",
                    "doc_type": "policy",
                    "enabled": True,
                }
            ]
        },
        owner_token,
    )
    assert code == 200, ("create_policy_job", code, job_body)
    job_data = job_body.get("data") or {}
    assert job_data.get("rule_set_id") == first_id, ("job_rule_set_id", job_data)
    assert "company_id" not in job_data, ("job_no_company_id", job_data)
    # settings response should use rule_set_id
    code, settings_body = request_json(
        "GET",
        f"/rule-sets/{first_id}/settings/system-prompt",
        token=owner_token,
    )
    assert code == 200, ("system_prompt_get", code, settings_body)
    settings_data = settings_body.get("data") or {}
    assert settings_data.get("rule_set_id") == first_id, ("settings_rule_set_id", settings_data)
    assert "company_id" not in settings_data, ("settings_no_company_id", settings_data)

    # old routes removed
    code, _ = request_json("GET", f"/companies/{first_id}/rule-suggestions", token=owner_token)
    assert code == 404, ("old_rule_suggestions_removed", code)

    code, _ = request_json("GET", f"/companies/{first_id}/policy-documents", token=owner_token)
    assert code == 404, ("old_policy_documents_removed", code)

    # members route removed from API
    code, _ = request_json("GET", f"/rule-sets/{first_id}/members", token=owner_token)
    assert code == 404, ("members_removed", code)

    print("ALL PASS: rule-set single-user smoke test")


if __name__ == "__main__":
    main()



