from __future__ import annotations

import time
from typing import Any

import httpx


API_BASE_URL = "http://localhost:8000".rstrip("/")
V1 = f"{API_BASE_URL}/v1"
TIMEOUT = 30.0
PWD = "123456"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_if_needed(client: httpx.Client, *, email: str, name: str) -> None:
    r = client.post(
        f"{V1}/auth/register",
        json={"email": email, "password": PWD, "name": name},
    )
    if r.status_code in (200, 201, 409):
        return
    fail(f"register failed: HTTP {r.status_code}\n{r.text}")


def login(client: httpx.Client, *, email: str) -> str:
    r = client.post(f"{V1}/auth/login", json={"email": email, "password": PWD})
    if r.status_code != 200:
        fail(f"login failed: HTTP {r.status_code}\n{r.text}")
    token = str(((r.json().get("data") or {}).get("access_token")) or "").strip()
    if not token:
        fail("missing access_token")
    return token


def create_personal_conversation(
    client: httpx.Client,
    token: str,
    *,
    title: str,
) -> dict[str, Any]:
    r = client.post(
        f"{V1}/conversations/personal",
        json={"title": title},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"create conversation failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def send_message(
    client: httpx.Client,
    token: str,
    *,
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


def list_conversations(
    client: httpx.Client,
    token: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    r = client.get(
        f"{V1}/conversations",
        params=params or {},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"list conversations failed: HTTP {r.status_code}\n{r.text}")
    return r.json()


def main() -> None:
    now = int(time.time())
    owner_email = f"conv.owner.{now}@test.com"
    other_email = f"conv.other.{now}@test.com"
    empty_email = f"conv.empty.{now}@test.com"

    with httpx.Client(timeout=TIMEOUT) as client:
        print("[1/11] register/login users")
        register_if_needed(client, email=owner_email, name="Conversation Owner")
        register_if_needed(client, email=other_email, name="Conversation Other")
        register_if_needed(client, email=empty_email, name="Conversation Empty")
        owner_token = login(client, email=owner_email)
        other_token = login(client, email=other_email)
        empty_token = login(client, email=empty_email)

        print("[2/11] list conversations empty state")
        empty_payload = list_conversations(client, empty_token)
        empty_data = empty_payload.get("data") or {}
        empty_items = list(empty_data.get("items") or [])
        if empty_items:
            fail(f"empty state should return no conversations: {empty_payload}")

        print("[3/11] create two conversations for owner")
        conv_a = create_personal_conversation(client, owner_token, title="Conversation A")
        conv_a_id = str(conv_a.get("id") or "").strip()
        if not conv_a_id:
            fail(f"missing conv_a id: {conv_a}")

        conv_b = create_personal_conversation(client, owner_token, title="Conversation B")
        conv_b_id = str(conv_b.get("id") or "").strip()
        if not conv_b_id:
            fail(f"missing conv_b id: {conv_b}")

        print("[4/11] send message and capture message id for detail API")
        sent = send_message(
            client,
            owner_token,
            conversation_id=conv_a_id,
            content="So dien thoai lien he cua toi la 0901234567",
        )
        sent_data = sent.get("data") or {}
        msg_id = str(sent_data.get("id") or "").strip()
        if not msg_id:
            fail(f"missing user message id from send response: {sent}")

        print("[5/11] list conversations pagination basic")
        first_page = list_conversations(client, owner_token, params={"limit": 1})
        page_data = first_page.get("data") or {}
        page_items = list(page_data.get("items") or [])
        page_meta = page_data.get("page") or {}
        if len(page_items) != 1:
            fail(f"limit=1 should return exactly one item: {first_page}")
        if not bool(page_meta.get("has_more")):
            fail(f"expected has_more=true for first page: {first_page}")
        next_before_updated_at = str(page_meta.get("next_before_updated_at") or "").strip()
        next_before_id = str(page_meta.get("next_before_id") or "").strip()
        if not (next_before_updated_at and next_before_id):
            fail(f"missing next page token: {first_page}")

        second_page = list_conversations(
            client,
            owner_token,
            params={
                "limit": 1,
                "before_updated_at": next_before_updated_at,
                "before_id": next_before_id,
            },
        )
        second_items = list(((second_page.get("data") or {}).get("items") or []))
        if len(second_items) != 1:
            fail(f"expected one item in second page: {second_page}")
        if str(second_items[0].get("id") or "") == str(page_items[0].get("id") or ""):
            fail(f"second page item should differ from first page item: {second_page}")

        print("[6/11] get conversation detail success and unauthorized/not-found case")
        ok_detail = client.get(
            f"{V1}/conversations/{conv_a_id}",
            headers=auth_headers(owner_token),
        )
        if ok_detail.status_code != 200:
            fail(f"owner get conversation detail failed: {ok_detail.status_code}\n{ok_detail.text}")

        denied_detail = client.get(
            f"{V1}/conversations/{conv_a_id}",
            headers=auth_headers(other_token),
        )
        if denied_detail.status_code not in (403, 404):
            fail(
                "non-owner get conversation detail should be forbidden/not-found: "
                f"{denied_detail.status_code}\n{denied_detail.text}"
            )

        print("[7/11] get message detail success")
        ok_message_detail = client.get(
            f"{V1}/conversations/{conv_a_id}/messages/{msg_id}",
            headers=auth_headers(owner_token),
        )
        if ok_message_detail.status_code != 200:
            fail(
                f"owner get message detail failed: {ok_message_detail.status_code}\n"
                f"{ok_message_detail.text}"
            )
        detail_data = (ok_message_detail.json().get("data") or {})
        if str(detail_data.get("id") or "") != msg_id:
            fail(f"message detail id mismatch: expected={msg_id}, got={detail_data}")

        print("[8/11] get message detail wrong conversation and wrong owner")
        wrong_conversation = client.get(
            f"{V1}/conversations/{conv_b_id}/messages/{msg_id}",
            headers=auth_headers(owner_token),
        )
        if wrong_conversation.status_code != 404:
            fail(
                "message should not be found in a different conversation: "
                f"{wrong_conversation.status_code}\n{wrong_conversation.text}"
            )

        wrong_owner = client.get(
            f"{V1}/conversations/{conv_a_id}/messages/{msg_id}",
            headers=auth_headers(other_token),
        )
        if wrong_owner.status_code not in (403, 404):
            fail(
                "non-owner get message detail should be forbidden/not-found: "
                f"{wrong_owner.status_code}\n{wrong_owner.text}"
            )

        print("[9/12] non-owner cannot send message into owner conversation")
        wrong_sender = client.post(
            f"{V1}/conversations/{conv_a_id}/messages",
            json={"content": "toi khong phai owner", "input_type": "user_input"},
            headers=auth_headers(other_token),
        )
        if wrong_sender.status_code not in (403, 404):
            fail(
                "non-owner send message should be forbidden/not-found: "
                f"{wrong_sender.status_code}\n{wrong_sender.text}"
            )

        print("[10/12] patch conversation title success")
        patched = client.patch(
            f"{V1}/conversations/{conv_b_id}",
            json={"title": "Conversation B Renamed"},
            headers=auth_headers(owner_token),
        )
        if patched.status_code != 200:
            fail(f"patch conversation failed: {patched.status_code}\n{patched.text}")
        patched_data = (patched.json().get("data") or {})
        if str(patched_data.get("title") or "") != "Conversation B Renamed":
            fail(f"patch title did not apply: {patched.json()}")

        print("[11/12] delete conversation (soft delete) success")
        deleted = client.delete(
            f"{V1}/conversations/{conv_b_id}",
            headers=auth_headers(owner_token),
        )
        if deleted.status_code != 200:
            fail(f"delete conversation failed: {deleted.status_code}\n{deleted.text}")
        deleted_data = (deleted.json().get("data") or {})
        if str(deleted_data.get("status") or "") != "archived":
            fail(f"soft delete must archive conversation: {deleted.json()}")

        print("[12/12] active filter excludes archived, archived filter returns archived")
        active_after_delete = list_conversations(client, owner_token, params={"status": "active"})
        active_items = list(((active_after_delete.get("data") or {}).get("items") or []))
        active_ids = {str(x.get("id") or "") for x in active_items}
        if conv_b_id in active_ids:
            fail(f"archived conversation should not appear in active list: {active_after_delete}")

        archived_list = list_conversations(
            client, owner_token, params={"status": "archived"}
        )
        archived_items = list(((archived_list.get("data") or {}).get("items") or []))
        archived_ids = {str(x.get("id") or "") for x in archived_items}
        if conv_b_id not in archived_ids:
            fail(f"archived conversation should appear in archived list: {archived_list}")

    print("ALL PASS: conversation workspace APIs are working for chat-first frontend MVP.")


if __name__ == "__main__":
    main()
