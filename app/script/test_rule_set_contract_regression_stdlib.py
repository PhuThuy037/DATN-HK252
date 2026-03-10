from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


BASE = "http://localhost:8000/v1"
PWD = "123456"


def request_json(
    method: str,
    path: str,
    data: dict | None = None,
    token: str | None = None,
):
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
    email = f"contract.rule-set.{now}@test.com"

    register(email, "Contract Rule Set")
    token = login(email)

    code, _ = request_json("GET", "/companies/me", token=token)
    assert code == 404, ("companies_removed", code)

    code, _ = request_json("GET", "/rules/personal", token=token)
    assert code == 404, ("personal_rules_removed", code)

    code, body = request_json(
        "POST",
        "/rule-sets",
        {"name": f"Contract Rule Set {now}"},
        token=token,
    )
    assert code == 200, ("create_rule_set", code, body)
    rule_set_id = ((body.get("data") or {}).get("id") or "").strip()
    assert rule_set_id, "missing rule_set id"

    code, created_rule_body = request_json(
        "POST",
        f"/rule-sets/{rule_set_id}/rules",
        {
            "stable_key": f"rule_set.contract.{now}",
            "name": "Contract Rule",
            "conditions": {"entity_type": "PHONE"},
            "action": "mask",
            "severity": "medium",
            "priority": 1,
            "rag_mode": "off",
            "enabled": True,
        },
        token=token,
    )
    assert code == 200, ("create_rule", code, created_rule_body)
    created_rule = created_rule_body.get("data") or {}
    assert created_rule.get("rule_set_id") == rule_set_id, (
        "rule_rule_set_id",
        created_rule,
    )
    assert "company_id" not in created_rule, ("rule_no_company_id", created_rule)

    code, conv_body = request_json(
        "POST",
        f"/rule-sets/{rule_set_id}/conversations",
        {"title": "contract conversation"},
        token=token,
    )
    assert code == 200, ("create_rule_set_conversation", code, conv_body)
    conv = conv_body.get("data") or {}
    assert conv.get("rule_set_id") == rule_set_id, ("conversation_rule_set_id", conv)
    assert "company_id" not in conv, ("conversation_no_company_id", conv)

    code, ok_scan = request_json(
        "POST",
        "/debug/full-scan",
        {"text": "so dien thoai 0901234567", "rule_set_id": rule_set_id},
        token=token,
    )
    assert code == 200, ("debug_full_scan_ok", code, ok_scan)
    assert ok_scan.get("ok") is True, ("debug_ok_flag", ok_scan)

    code, bad_scan = request_json(
        "POST",
        "/debug/full-scan",
        {"text": "so dien thoai 0901234567", "company_id": rule_set_id},
        token=token,
    )
    assert code == 422, ("debug_company_id_rejected", code, bad_scan)

    print("ALL PASS: rule-set contract regression is working")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
