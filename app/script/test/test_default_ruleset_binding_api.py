from __future__ import annotations

import os
import time
from typing import Any
from uuid import UUID

import httpx
from sqlmodel import Session, select

import app.db.all_models  # noqa: F401
from app.auth.model import User
from app.auth.passwords import hash_password
from app.common.enums import SystemRole, UserStatus
from app.company import service as company_service
from app.company.model import Company
from app.core.config import get_settings
from app.db.engine import engine


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
V1 = f"{API_BASE_URL}/v1"
TIMEOUT = float(os.getenv("API_TIMEOUT_SECONDS", "30"))
PWD = os.getenv("TEST_USER_PASSWORD", "123456")


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
        row = session.exec(
            select(User).where(User.email == email.strip().lower())
        ).first()
        if row is None:
            row = User(
                email=email.strip().lower(),
                hashed_password=hash_password(password),
                name="Default Rule Source Admin",
                status=UserStatus.active,
                role=SystemRole.admin,
            )
        else:
            row.name = row.name or "Default Rule Source Admin"
            row.status = UserStatus.active
            row.role = SystemRole.admin
            row.hashed_password = hash_password(password)

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
            name=f"Default Rule Source {int(time.time())}",
        )
        return company


def create_rule(
    client: httpx.Client,
    *,
    token: str,
    rule_set_id: str,
    token_term: str,
) -> dict[str, Any]:
    payload = {
        "rule": {
            "stable_key": f"default.scope.user.block.{int(time.time())}",
            "name": "Default rule source block",
            "description": "Block internal code token from default admin rule set",
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
        fail(f"create rule failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


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
        fail(f"create personal conversation failed: HTTP {r.status_code}\n{r.text}")
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


def get_message_detail(
    client: httpx.Client,
    token: str,
    *,
    conversation_id: str,
    message_id: str,
) -> dict[str, Any]:
    r = client.get(
        f"{V1}/conversations/{conversation_id}/messages/{message_id}",
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"get message detail failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def main() -> None:
    settings = get_settings()
    admin_email = str(settings.default_ruleset_admin_email or "").strip().lower()
    if not admin_email:
        fail("DEFAULT_RULESET_ADMIN_EMAIL must be configured for this smoke test")

    print("[setup] ensure default admin account + active rule set")
    admin = _upsert_default_admin(email=admin_email, password=PWD)
    default_rule_set = _ensure_default_rule_set(admin_user_id=admin.id)

    now = int(time.time())
    user_email = f"default.scope.user.{now}@test.com"
    other_email = f"default.scope.other.{now}@test.com"
    token_term = f"ZXQ-DEFAULT-{now}"

    with httpx.Client(timeout=TIMEOUT) as client:
        print("[1/6] register/login users")
        register_if_needed(client, email=user_email, name="Default Scope User")
        register_if_needed(client, email=other_email, name="Default Scope Other")
        admin_token = login(client, email=admin_email)
        user_token = login(client, email=user_email)
        other_token = login(client, email=other_email)

        print("[2/6] admin creates scoped block rule in default rule set")
        created_rule = create_rule(
            client,
            token=admin_token,
            rule_set_id=str(default_rule_set.id),
            token_term=token_term,
        )
        created_rule_id = str(created_rule.get("id") or "").strip()
        if not created_rule_id:
            fail(f"missing created rule id: {created_rule}")

        print("[3/6] user creates personal conversation bound to default rule set")
        conversation = create_personal_conversation(
            client,
            user_token,
            title="Default rule source binding",
        )
        conversation_id = str(conversation.get("id") or "").strip()
        if not conversation_id:
            fail(f"missing conversation id: {conversation}")
        bound_rule_set_id = str(conversation.get("rule_set_id") or "").strip()
        if bound_rule_set_id != str(default_rule_set.id):
            fail(
                "personal conversation should bind to default rule set: "
                f"expected={default_rule_set.id} got={bound_rule_set_id or None}"
            )

        print("[4/6] user message now hits admin default rule source")
        sent = send_message(
            client,
            user_token,
            conversation_id=conversation_id,
            content=f"Toi co ma noi bo {token_term.lower()} can duoc chan",
        )
        if sent.get("ok") is not False:
            fail(f"blocked user message should return ok=false: {sent}")
        sent_data = sent.get("data") or {}
        if str(sent_data.get("final_action") or "").lower() != "block":
            fail(f"expected final_action=block: {sent}")
        message_id = str(sent_data.get("id") or "").strip()
        if not message_id:
            fail(f"missing user message id in send response: {sent}")

        detail = get_message_detail(
            client,
            user_token,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        matched_rule_ids = {str(x) for x in list(detail.get("matched_rule_ids") or [])}
        if created_rule_id not in matched_rule_ids:
            fail(
                "user flow should match admin scoped rule from default rule set: "
                f"detail={detail}"
            )

        print("[5/6] ownership stays with creator")
        owner_id = str(conversation.get("user_id") or "").strip()
        with Session(engine) as session:
            user_row = session.exec(select(User).where(User.email == user_email)).first()
            if user_row is None:
                fail("user row not found after conversation create")
            if owner_id != str(user_row.id):
                fail(f"conversation owner mismatch: expected={user_row.id}, got={owner_id}")

        print("[6/6] another user still cannot access the conversation")
        denied = client.get(
            f"{V1}/conversations/{conversation_id}",
            headers=auth_headers(other_token),
        )
        if denied.status_code not in (403, 404):
            fail(
                "other user should not access bound conversation: "
                f"{denied.status_code}\n{denied.text}"
            )

    print("ALL PASS: default rule set binding works for user runtime.")


if __name__ == "__main__":
    main()
