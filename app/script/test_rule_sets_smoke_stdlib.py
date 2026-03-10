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

    # idempotent create
    code, body = request_json(
        "POST", "/rule-sets", {"name": "Demo Rule Set 2"}, owner_token
    )
    assert code == 200, ("create_rule_set_again", code, body)
    second_id = ((body.get("data") or {}).get("id") or "").strip()
    assert first_id == second_id, ("idempotent", first_id, second_id)

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



