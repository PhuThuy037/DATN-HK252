from __future__ import annotations

import time

import httpx


BASE = "http://localhost:8000/v1"
PWD = "123456"


def register(client: httpx.Client, *, email: str, name: str) -> None:
    r = client.post(
        f"{BASE}/auth/register",
        json={"email": email, "password": PWD, "name": name},
    )
    assert r.status_code in (200, 409), ("register", r.status_code, r.text)


def login(client: httpx.Client, *, email: str) -> str:
    r = client.post(f"{BASE}/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, ("login", r.status_code, r.text)
    return r.json()["data"]["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    now = int(time.time())
    owner_email = f"owner.rules.{now}@test.com"
    other_email = f"other.rules.{now}@test.com"

    with httpx.Client(timeout=30) as client:
        register(client, email=owner_email, name="Owner")
        register(client, email=other_email, name="Other")

        owner_token = login(client, email=owner_email)
        other_token = login(client, email=other_email)

        # Personal-rules API has been removed.
        r = client.get(f"{BASE}/rules/personal", headers=headers(owner_token))
        assert r.status_code == 404, ("personal_rules_removed", r.status_code, r.text)

        r = client.post(
            f"{BASE}/rule-sets",
            headers=headers(owner_token),
            json={"name": f"Owner Rule Set {now}"},
        )
        assert r.status_code == 200, ("create_rule_set", r.status_code, r.text)
        first_id = (r.json().get("data") or {}).get("id")
        assert first_id, "missing rule_set id"

        # Create again must fail clearly (no silent reuse).
        r = client.post(
            f"{BASE}/rule-sets",
            headers=headers(owner_token),
            json={"name": f"Owner Rule Set renamed {now}"},
        )
        assert r.status_code == 409, ("create_rule_set_again", r.status_code, r.text)
        err = (r.json().get("error") or {})
        assert err.get("code") == "RULE_SET_ALREADY_EXISTS", ("error_code", err)

        r = client.get(f"{BASE}/rule-sets/{first_id}/rules", headers=headers(owner_token))
        assert r.status_code == 200, ("owner_list_rules", r.status_code, r.text)

        # Member APIs are removed in single-user mode.
        r = client.get(f"{BASE}/rule-sets/{first_id}/members", headers=headers(owner_token))
        assert r.status_code == 404, ("members_route_removed", r.status_code, r.text)

        # Non-owner cannot access owner rule set resources.
        r = client.get(f"{BASE}/rule-sets/{first_id}/rules", headers=headers(other_token))
        assert r.status_code == 403, ("other_user_forbidden", r.status_code, r.text)

    print("ALL PASS: single-user rule-set mode works as expected")


if __name__ == "__main__":
    main()
