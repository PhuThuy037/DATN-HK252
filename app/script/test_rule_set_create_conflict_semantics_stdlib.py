from __future__ import annotations

import json
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
    email = f"ruleset.create.conflict.{now}@test.com"
    first_name = f"Manual RAG RuleSet A {now}"
    second_name = f"Manual RAG RuleSet B {now}"

    register(email, "RuleSet Create Conflict")
    token = login(email)

    # Case 1: user has no active personal rule set -> create succeeds.
    code, first_body = request_json(
        "POST",
        "/rule-sets",
        {"name": first_name},
        token=token,
    )
    assert code == 200, ("create_first", code, first_body)
    assert first_body.get("ok") is True, ("create_first_ok", first_body)
    first_data = first_body.get("data") or {}
    first_id = str(first_data.get("id") or "").strip()
    assert first_id, ("create_first_missing_id", first_body)
    assert first_data.get("name") == first_name, (
        "create_first_name_mismatch",
        first_data,
        first_name,
    )

    # Case 2: user already has active personal rule set -> 409 + clear error.
    code, second_body = request_json(
        "POST",
        "/rule-sets",
        {"name": second_name},
        token=token,
    )
    assert code == 409, ("create_second_status", code, second_body)
    assert second_body.get("ok") is False, ("create_second_ok_flag", second_body)
    assert second_body.get("data") in (None, {}), ("create_second_data_must_be_empty", second_body)

    err = second_body.get("error") or {}
    assert err.get("code") == "RULE_SET_ALREADY_EXISTS", ("create_second_error_code", err)
    assert err.get("message") == "User already has an active personal rule set", (
        "create_second_error_message",
        err,
    )

    # Case 3: GET /rule-sets/me still works and returns existing set.
    code, list_body = request_json("GET", "/rule-sets/me", token=token)
    assert code == 200, ("list_my_rule_sets_status", code, list_body)
    assert list_body.get("ok") is True, ("list_my_rule_sets_ok", list_body)
    items = list_body.get("data") or []
    assert isinstance(items, list), ("list_my_rule_sets_data_type", type(items), list_body)
    assert len(items) == 1, ("list_my_rule_sets_size", len(items), items)

    item = items[0] or {}
    assert str(item.get("id") or "") == first_id, ("list_my_rule_sets_id", item, first_id)
    assert item.get("name") == first_name, ("list_my_rule_sets_name", item, first_name)

    print("ALL PASS: create conflict semantics for /v1/rule-sets")


if __name__ == "__main__":
    main()

