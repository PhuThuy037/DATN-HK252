from __future__ import annotations

import os
import time
from uuid import UUID

import httpx
from sqlmodel import Session, select

import app.db.all_models  # noqa: F401
from app.auth.model import User
from app.auth.passwords import hash_password
from app.common.enums import (
    MessageInputType,
    MessageRole,
    RuleAction,
    ScanStatus,
    SystemRole,
    UserStatus,
)
from app.company import service as company_service
from app.company.model import Company
from app.conversation import service as conversation_service
from app.core.config import get_settings
from app.db.engine import engine
from app.messages.model import Message


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
TIMEOUT = float(os.getenv("API_TIMEOUT_SECONDS", "30"))
PWD = os.getenv("TEST_USER_PASSWORD", "123456")
BLOCKED_PLACEHOLDER = "Content was blocked by the active compliance policy."


def fail(msg: str) -> None:
    raise AssertionError(msg)


def auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "accept": "application/json",
        "content-type": "application/json",
    }


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


def _upsert_default_admin(*, email: str, password: str) -> User:
    with Session(engine) as session:
        row = session.exec(select(User).where(User.email == email.strip().lower())).first()
        if row is None:
            row = User(
                email=email.strip().lower(),
                hashed_password=hash_password(password),
                name="Default Rule Source Admin",
                status=UserStatus.active,
                role=SystemRole.admin,
            )
        else:
            row.status = UserStatus.active
            row.role = SystemRole.admin
            row.hashed_password = hash_password(password)
            row.name = row.name or "Default Rule Source Admin"
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def _ensure_default_rule_set(*, admin_user_id: UUID) -> Company:
    with Session(engine) as session:
        rows = company_service.list_my_companies(session=session, user_id=admin_user_id)
        if rows:
            return rows[0][0]
        company, _ = company_service.create_company(
            session=session,
            user_id=admin_user_id,
            name=f"Blocked Persistence {int(time.time())}",
        )
        return company


def create_scoped_block_rule(
    client: httpx.Client,
    *,
    token: str,
    rule_set_id: str,
    token_term: str,
) -> str:
    payload = {
        "rule": {
            "stable_key": f"blocked.persistence.{int(time.time())}",
            "name": "Blocked persistence test",
            "description": "Block internal code token for persistence test",
            "scope": "chat",
            "conditions": {
                "all": [
                    {
                        "signal": {
                            "field": "context_keywords",
                            "any_of": [token_term.lower()],
                        }
                    }
                ]
            },
            "action": "block",
            "severity": "high",
            "priority": 999,
            "rag_mode": "off",
            "enabled": True,
        },
        "context_terms": [
            {
                "entity_type": "INTERNAL_CODE",
                "term": token_term.lower(),
                "lang": "vi",
                "weight": 1,
                "window_1": 60,
                "window_2": 20,
                "enabled": True,
            }
        ],
    }
    r = client.post(
        f"{V1}/rule-sets/{rule_set_id}/rules",
        json=payload,
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"create scoped block rule failed: HTTP {r.status_code}\n{r.text}")
    out = r.json().get("data") or {}
    rule_id = str(out.get("id") or "").strip()
    if not rule_id:
        fail(f"missing rule id from create response: {out}")
    return rule_id


def create_personal_conversation(client: httpx.Client, token: str, *, title: str) -> dict:
    r = client.post(
        f"{V1}/conversations/personal",
        json={"title": title},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"create personal conversation failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def get_messages(client: httpx.Client, token: str, *, conversation_id: str) -> dict:
    r = client.get(
        f"{V1}/conversations/{conversation_id}/messages",
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"get messages failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def get_message_detail(
    client: httpx.Client,
    token: str,
    *,
    conversation_id: str,
    message_id: str,
) -> dict:
    r = client.get(
        f"{V1}/conversations/{conversation_id}/messages/{message_id}",
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"get message detail failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def send_message(
    client: httpx.Client,
    token: str,
    *,
    conversation_id: str,
    content: str,
) -> dict:
    r = client.post(
        f"{V1}/conversations/{conversation_id}/messages",
        json={"content": content, "input_type": "user_input"},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"send message failed: HTTP {r.status_code}\n{r.text}")
    return r.json()


def main() -> None:
    settings = get_settings()
    admin_email = str(settings.default_ruleset_admin_email or "").strip().lower()
    if not admin_email:
        fail("DEFAULT_RULESET_ADMIN_EMAIL must be configured for this test")

    print("[setup] ensure default admin account and rule set")
    admin = _upsert_default_admin(email=admin_email, password=PWD)
    default_rule_set = _ensure_default_rule_set(admin_user_id=admin.id)

    now = int(time.time())
    user_email = f"blocked.persistence.user.{now}@test.com"
    other_email = f"blocked.persistence.other.{now}@test.com"
    token_term = f"ZXQ-BLOCKED-{now}"
    blocked_text = f"Ma noi bo can chan la {token_term.lower()}"

    with httpx.Client(timeout=TIMEOUT) as client:
        print("[1/8] register/login users")
        register_if_needed(client, email=user_email, name="Blocked Persistence User")
        register_if_needed(client, email=other_email, name="Blocked Persistence Other")
        admin_token = login(client, email=admin_email)
        user_token = login(client, email=user_email)
        other_token = login(client, email=other_email)

        print("[2/8] admin creates scoped block rule in default rule set")
        created_rule_id = create_scoped_block_rule(
            client,
            token=admin_token,
            rule_set_id=str(default_rule_set.id),
            token_term=token_term,
        )

        print("[3/8] user creates personal conversation and sends blocked content")
        conversation = create_personal_conversation(
            client,
            user_token,
            title="Blocked persistence conversation",
        )
        conversation_id = str(conversation.get("id") or "").strip()
        if not conversation_id:
            fail(f"missing conversation id: {conversation}")

        send_body = send_message(
            client,
            user_token,
            conversation_id=conversation_id,
            content=blocked_text,
        )
        if send_body.get("ok") is not False:
            fail(f"blocked send should return ok=false: {send_body}")
        send_data = send_body.get("data") or {}
        message_id = str(send_data.get("id") or "").strip()
        if not message_id:
            fail(f"missing blocked message id: {send_body}")
        if send_data.get("content") not in (None, ""):
            fail(f"user send response must not expose raw blocked content: {send_body}")
        if blocked_text in str(send_body):
            fail(f"user send response leaked blocked raw content: {send_body}")
        if str(send_data.get("final_action") or "").lower() != "block":
            fail(f"expected blocked final_action in send response: {send_body}")

        print("[4/8] raw blocked content is persisted in DB")
        with Session(engine) as session:
            row = session.get(Message, UUID(message_id))
            if row is None:
                fail("blocked message row not found")
            if row.content != blocked_text:
                fail(f"raw blocked content not persisted correctly: stored={row.content!r}")
            if not row.content_hash:
                fail("blocked message should still persist content_hash")

        print("[5/8] user-facing projections still hide raw blocked content")
        messages_page = get_messages(
            client,
            user_token,
            conversation_id=conversation_id,
        )
        items = list(messages_page.get("items") or [])
        target_list_item = next(
            (item for item in items if str(item.get("id") or "") == message_id),
            None,
        )
        if target_list_item is None:
            fail(f"blocked message missing from user messages page: {messages_page}")
        if target_list_item.get("state") != "blocked":
            fail(f"blocked message should have state=blocked: {target_list_item}")
        if blocked_text in str(target_list_item):
            fail(f"user messages page leaked blocked raw content: {target_list_item}")

        detail = get_message_detail(
            client,
            user_token,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        if detail.get("content") not in (None, ""):
            fail(f"user message detail must not expose raw blocked content: {detail}")
        if blocked_text in str(detail):
            fail(f"user message detail leaked blocked raw content: {detail}")

        print("[6/8] admin monitoring surfaces expose raw blocked content")
        admin_messages_resp = client.get(
            f"{V1}/admin/conversations/{conversation_id}/messages",
            headers=auth_headers(admin_token),
        )
        if admin_messages_resp.status_code != 200:
            fail(
                "admin conversation messages failed: "
                f"{admin_messages_resp.status_code}\n{admin_messages_resp.text}"
            )
        admin_items = list(((admin_messages_resp.json().get("data") or {}).get("items")) or [])
        admin_target = next(
            (item for item in admin_items if str(item.get("id") or "") == message_id),
            None,
        )
        if admin_target is None:
            fail(f"admin messages missing blocked target: {admin_messages_resp.text}")
        if admin_target.get("content") != blocked_text:
            fail(f"admin messages should expose raw blocked content: {admin_target}")
        matched_rule_ids = {str(x) for x in list(admin_target.get("matched_rule_ids") or [])}
        if created_rule_id not in matched_rule_ids:
            fail(f"expected admin message detail to show matching rule id: {admin_target}")

        logs_resp = client.get(
            f"{V1}/admin/logs/block-mask",
            headers=auth_headers(admin_token),
        )
        if logs_resp.status_code != 200:
            fail(f"admin block-mask logs failed: {logs_resp.status_code}\n{logs_resp.text}")
        log_items = list(logs_resp.json().get("data") or [])
        target_log = next(
            (item for item in log_items if str(item.get("message_id") or "") == message_id),
            None,
        )
        if target_log is None:
            fail(f"blocked message missing from admin logs: {logs_resp.text}")
        if target_log.get("content") != blocked_text:
            fail(f"admin log should expose raw blocked content: {target_log}")

        print("[7/8] admin routes remain admin-only")
        denied = client.get(
            f"{V1}/admin/conversations/{conversation_id}/messages",
            headers=auth_headers(other_token),
        )
        if denied.status_code != 403:
            fail(f"non-admin should be denied admin messages route: {denied.status_code}\n{denied.text}")

        print("[8/8] non-block projection helpers remain stable for mask/allow flows")
        allow_message = Message(
            conversation_id=UUID(conversation_id),
            role=MessageRole.user,
            sequence_number=100,
            input_type=MessageInputType.user_input,
            content="hello world",
            content_masked=None,
            scan_status=ScanStatus.done,
            final_action=RuleAction.allow,
        )
        allow_safe = conversation_service.build_safe_message_detail(message=allow_message)
        if allow_safe.get("content") != "hello world":
            fail(f"allow projection regressed: {allow_safe}")

        mask_message = Message(
            conversation_id=UUID(conversation_id),
            role=MessageRole.user,
            sequence_number=101,
            input_type=MessageInputType.user_input,
            content="0901234567",
            content_masked="[MASKED PHONE]",
            scan_status=ScanStatus.done,
            final_action=RuleAction.mask,
        )
        mask_safe = conversation_service.build_safe_message_detail(message=mask_message)
        if mask_safe.get("content") != "[MASKED PHONE]":
            fail(f"mask projection regressed: {mask_safe}")

        blocked_message = Message(
            conversation_id=UUID(conversation_id),
            role=MessageRole.user,
            sequence_number=102,
            input_type=MessageInputType.user_input,
            content=blocked_text,
            content_masked=None,
            scan_status=ScanStatus.done,
            final_action=RuleAction.block,
        )
        admin_blocked = conversation_service.build_admin_message_detail(
            message=blocked_message
        )
        user_blocked = conversation_service.build_safe_message_detail(
            message=blocked_message
        )
        if admin_blocked.get("content") != blocked_text:
            fail(f"admin blocked projection regressed: {admin_blocked}")
        if user_blocked.get("content") not in (None, ""):
            fail(f"user blocked projection must stay hidden: {user_blocked}")

    print(
        "ALL PASS: blocked message persistence keeps raw content for admin while user surfaces stay safe."
    )


if __name__ == "__main__":
    main()
