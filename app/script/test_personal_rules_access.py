from __future__ import annotations

import time

import httpx


BASE = "http://localhost:8000/v1"
PWD = "123456"
PHONE_TEXT = "So dien thoai test 0901234567"
PHONE_RULE_KEY = "global.pii.phone.mask"


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


def create_personal_conversation(client: httpx.Client, token: str) -> str:
    r = client.post(
        f"{BASE}/conversations/personal",
        headers=headers(token),
        json={"title": "personal-rules-check"},
    )
    assert r.status_code == 200, ("create_personal_conversation", r.status_code, r.text)
    return r.json()["data"]["id"]


def send_message(
    client: httpx.Client,
    token: str,
    conversation_id: str,
    content: str,
) -> dict:
    r = client.post(
        f"{BASE}/conversations/{conversation_id}/messages",
        headers=headers(token),
        json={"content": content, "input_type": "user_input"},
    )
    assert r.status_code == 200, ("send_message_http", r.status_code, r.text)
    return r.json()


def matched_stable_keys(message_response: dict) -> list[str]:
    data = message_response.get("data") or {}
    entities_json = data.get("entities_json") or {}
    matched = entities_json.get("matched_rules") or []
    return [str(x.get("stable_key") or "") for x in matched]


def main() -> None:
    now = int(time.time())
    solo_email = f"solo.rules.{now}@test.com"
    admin_email = f"admin.rules.{now}@test.com"
    member_email = f"member.rules.{now}@test.com"

    with httpx.Client(timeout=30) as client:
        # non-company user can list + toggle personal
        register(client, email=solo_email, name="Solo Rules")
        solo_token = login(client, email=solo_email)

        r = client.get(f"{BASE}/rules/personal", headers=headers(solo_token))
        assert r.status_code == 200, ("solo_list_personal", r.status_code, r.text)
        personal_rules = r.json().get("data") or []
        assert personal_rules, "expected non-empty personal rules"

        r = client.patch(
            f"{BASE}/rules/personal/{PHONE_RULE_KEY}/enabled",
            headers=headers(solo_token),
            json={"enabled": False},
        )
        assert r.status_code == 200, ("solo_toggle_off", r.status_code, r.text)
        assert (r.json()["data"] or {}).get("enabled") is False

        conv_id = create_personal_conversation(client, solo_token)
        res_off = send_message(client, solo_token, conv_id, PHONE_TEXT)
        keys_off = matched_stable_keys(res_off)
        assert PHONE_RULE_KEY not in keys_off, (
            "phone_rule_should_not_apply_after_toggle_off",
            keys_off,
            res_off,
        )

        r = client.patch(
            f"{BASE}/rules/personal/{PHONE_RULE_KEY}/enabled",
            headers=headers(solo_token),
            json={"enabled": True},
        )
        assert r.status_code == 200, ("solo_toggle_on", r.status_code, r.text)
        assert (r.json()["data"] or {}).get("enabled") is True

        conv_id2 = create_personal_conversation(client, solo_token)
        res_on = send_message(client, solo_token, conv_id2, PHONE_TEXT)
        keys_on = matched_stable_keys(res_on)
        assert PHONE_RULE_KEY in keys_on, (
            "phone_rule_should_apply_after_toggle_on",
            keys_on,
            res_on,
        )

        # company member can view company rules, cannot use personal endpoint or toggle
        register(client, email=admin_email, name="Admin Rules")
        register(client, email=member_email, name="Member Rules")
        admin_token = login(client, email=admin_email)
        member_token = login(client, email=member_email)

        r = client.post(
            f"{BASE}/companies",
            headers=headers(admin_token),
            json={"name": f"Rules Company {now}"},
        )
        assert r.status_code == 200, ("create_company", r.status_code, r.text)
        company_id = r.json()["data"]["id"]

        r = client.post(
            f"{BASE}/companies/{company_id}/members",
            headers=headers(admin_token),
            json={"email": member_email},
        )
        assert r.status_code == 200, ("add_member", r.status_code, r.text)

        r = client.get(
            f"{BASE}/companies/{company_id}/rules", headers=headers(member_token)
        )
        assert r.status_code == 200, (
            "member_view_company_rules",
            r.status_code,
            r.text,
        )

        r = client.patch(
            f"{BASE}/companies/{company_id}/rules/global/{PHONE_RULE_KEY}/enabled",
            headers=headers(member_token),
            json={"enabled": False},
        )
        assert r.status_code == 403, (
            "member_company_toggle_forbidden",
            r.status_code,
            r.text,
        )

        r = client.get(f"{BASE}/rules/personal", headers=headers(member_token))
        assert r.status_code == 403, (
            "member_personal_view_forbidden",
            r.status_code,
            r.text,
        )

        r = client.patch(
            f"{BASE}/rules/personal/{PHONE_RULE_KEY}/enabled",
            headers=headers(member_token),
            json={"enabled": False},
        )
        assert r.status_code == 403, (
            "member_personal_toggle_forbidden",
            r.status_code,
            r.text,
        )

    print("ALL PASS: personal/company rule access policy works as expected")


if __name__ == "__main__":
    main()
