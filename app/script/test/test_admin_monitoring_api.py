from __future__ import annotations

import time
from uuid import UUID, uuid4

import httpx
from sqlmodel import Session
from sqlmodel import select

from app.auth.model import User
from app.common.enums import (
    MessageInputType,
    MessageRole,
    RagMode,
    RuleAction,
    RuleScope,
    RuleSeverity,
    ScanStatus,
    SystemRole,
)
from app.company.model import Company
from app.conversation.model import Conversation
from app.db.engine import engine
from app.messages.model import Message
from app.rag.models.rag_retrieval_log import RagRetrievalLog
from app.rule.model import Rule
from app.rule_change_log.model import RuleChangeLog

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
) -> dict:
    r = client.post(
        f"{V1}/conversations/personal",
        json={"title": title},
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        fail(f"create conversation failed: HTTP {r.status_code}\n{r.text}")
    return r.json().get("data") or {}


def promote_user_to_admin(email: str) -> None:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            fail(f"admin candidate not found: {email}")
        user.role = SystemRole.admin
        session.add(user)
        session.commit()


def seed_monitoring_rows(*, conversation_id: str, owner_email: str, admin_email: str) -> None:
    with Session(engine) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).first()
        admin = session.exec(select(User).where(User.email == admin_email)).first()
        conversation = session.get(Conversation, UUID(conversation_id))
        if not owner or not admin or not conversation:
            fail("seed prerequisites missing")

        rule_id = uuid4()
        blocked_rule = {
            "rule_id": str(rule_id),
            "stable_key": "monitoring.demo.block",
            "name": "Monitoring Demo Block",
            "action": "block",
            "priority": 90,
        }
        masked_rule = {
            "rule_id": str(rule_id),
            "stable_key": "monitoring.demo.mask",
            "name": "Monitoring Demo Mask",
            "action": "mask",
            "priority": 70,
        }

        message_block = Message(
            conversation_id=conversation.id,
            role=MessageRole.user,
            sequence_number=1,
            input_type=MessageInputType.user_input,
            content=None,
            content_masked=None,
            scan_status=ScanStatus.done,
            final_action=RuleAction.block,
            risk_score=0.97,
            ambiguous=False,
            matched_rule_ids=[str(rule_id)],
            entities_json={"matched_rules": [blocked_rule], "signals": {"source": "seed"}},
            rag_evidence_json=None,
            latency_ms=21,
        )
        session.add(message_block)
        session.flush()

        message_mask = Message(
            conversation_id=conversation.id,
            role=MessageRole.assistant,
            sequence_number=2,
            input_type=MessageInputType.tool_result,
            content="API key sk-live-monitoring-demo",
            content_masked="[MASKED API KEY]",
            scan_status=ScanStatus.done,
            final_action=RuleAction.mask,
            risk_score=0.65,
            ambiguous=False,
            matched_rule_ids=[str(rule_id)],
            entities_json={"matched_rules": [masked_rule], "signals": {"source": "seed"}},
            rag_evidence_json={"policy": "seed-demo"},
            latency_ms=17,
        )
        session.add(message_mask)
        session.flush()

        conversation.last_sequence_number = 2
        session.add(conversation)

        retrieval_log = RagRetrievalLog(
            message_id=message_mask.id,
            query="demo retrieval query",
            top_k=3,
            results_json={"results": [{"chunk_id": "demo-1"}, {"chunk_id": "demo-2"}]},
            latency_ms=42,
        )
        session.add(retrieval_log)

        company = Company(name=f"monitoring-demo-{int(time.time())}")
        session.add(company)
        session.flush()

        rule = Rule(
            company_id=company.id,
            stable_key=f"monitoring.demo.rule.{uuid4()}",
            name="Monitoring Audit Rule",
            description="Seeded for admin audit monitoring",
            scope=RuleScope.chat,
            conditions={"contains": "demo"},
            action=RuleAction.mask,
            severity=RuleSeverity.medium,
            priority=5,
            rag_mode=RagMode.off,
            enabled=True,
            is_deleted=False,
            created_by=admin.id,
        )
        session.add(rule)
        session.flush()

        audit_log = RuleChangeLog(
            company_id=company.id,
            rule_id=rule.id,
            actor_user_id=admin.id,
            action="create",
            changed_fields=["name", "action"],
            before_json=None,
            after_json={"name": rule.name, "action": rule.action.value},
        )
        session.add(audit_log)
        session.commit()


def main() -> None:
    now = int(time.time())
    admin_email = f"monitor.admin.{now}@test.com"
    owner_email = f"monitor.owner.{now}@test.com"
    other_email = f"monitor.other.{now}@test.com"

    with httpx.Client(timeout=TIMEOUT) as client:
        print("[1/8] register users")
        register_if_needed(client, email=admin_email, name="Monitor Admin")
        register_if_needed(client, email=owner_email, name="Monitor Owner")
        register_if_needed(client, email=other_email, name="Monitor Other")

        print("[2/8] promote admin account")
        promote_user_to_admin(admin_email)

        print("[3/8] login users")
        admin_token = login(client, email=admin_email)
        owner_token = login(client, email=owner_email)
        other_token = login(client, email=other_email)

        print("[4/8] create owner conversation and seed monitoring rows")
        conversation = create_personal_conversation(
            client,
            owner_token,
            title="Admin monitoring target",
        )
        conversation_id = str(conversation.get("id") or "").strip()
        if not conversation_id:
            fail(f"missing conversation id: {conversation}")
        seed_monitoring_rows(
            conversation_id=conversation_id,
            owner_email=owner_email,
            admin_email=admin_email,
        )

        print("[5/8] user is denied from admin monitoring routes")
        denied = client.get(
            f"{V1}/admin/conversations",
            headers=auth_headers(other_token),
        )
        if denied.status_code != 403:
            fail(f"user must be denied admin conversations: {denied.status_code}\n{denied.text}")
        denied_block_mask = client.get(
            f"{V1}/admin/logs/block-mask",
            headers=auth_headers(other_token),
        )
        if denied_block_mask.status_code != 403:
            fail(
                "user must be denied block/mask logs: "
                f"{denied_block_mask.status_code}\n{denied_block_mask.text}"
            )
        denied_retrieval = client.get(
            f"{V1}/admin/logs/rag-retrieval",
            headers=auth_headers(other_token),
        )
        if denied_retrieval.status_code != 403:
            fail(
                "user must be denied rag retrieval logs: "
                f"{denied_retrieval.status_code}\n{denied_retrieval.text}"
            )
        denied_audit = client.get(
            f"{V1}/admin/logs/audit",
            headers=auth_headers(other_token),
        )
        if denied_audit.status_code != 403:
            fail(
                "user must be denied audit logs: "
                f"{denied_audit.status_code}\n{denied_audit.text}"
            )

        print("[6/8] admin can monitor conversation list/detail/messages")
        list_resp = client.get(
            f"{V1}/admin/conversations",
            headers=auth_headers(admin_token),
        )
        if list_resp.status_code != 200:
            fail(f"admin conversations failed: {list_resp.status_code}\n{list_resp.text}")
        list_items = list((list_resp.json().get("data") or []))
        target = next((row for row in list_items if str(row.get("id") or "") == conversation_id), None)
        if not target:
            fail(f"admin list missing target conversation: {list_resp.text}")
        if str(target.get("user_email") or "") != owner_email:
            fail(f"admin list should expose owner email: {target}")

        detail_resp = client.get(
            f"{V1}/admin/conversations/{conversation_id}",
            headers=auth_headers(admin_token),
        )
        if detail_resp.status_code != 200:
            fail(f"admin conversation detail failed: {detail_resp.status_code}\n{detail_resp.text}")

        messages_resp = client.get(
            f"{V1}/admin/conversations/{conversation_id}/messages",
            headers=auth_headers(admin_token),
        )
        if messages_resp.status_code != 200:
            fail(f"admin conversation messages failed: {messages_resp.status_code}\n{messages_resp.text}")
        message_items = list((((messages_resp.json().get("data") or {}).get("items")) or []))
        if len(message_items) < 2:
            fail(f"expected seeded messages in admin detail: {messages_resp.text}")

        print("[7/8] user route still blocks cross-user conversation access")
        wrong_owner = client.get(
            f"{V1}/conversations/{conversation_id}",
            headers=auth_headers(other_token),
        )
        if wrong_owner.status_code not in (403, 404):
            fail(f"user route should deny cross-user conversation: {wrong_owner.status_code}\n{wrong_owner.text}")

        print("[8/8] admin monitoring logs return seeded data")
        block_mask_resp = client.get(
            f"{V1}/admin/logs/block-mask",
            headers=auth_headers(admin_token),
        )
        if block_mask_resp.status_code != 200:
            fail(f"admin block/mask logs failed: {block_mask_resp.status_code}\n{block_mask_resp.text}")
        block_mask_items = list(block_mask_resp.json().get("data") or [])
        actions = {str(item.get("action") or "") for item in block_mask_items if str(item.get("conversation_id") or "") == conversation_id}
        if "block" not in actions or "mask" not in actions:
            fail(f"expected block and mask items in admin log list: {block_mask_resp.text}")

        retrieval_resp = client.get(
            f"{V1}/admin/logs/rag-retrieval",
            headers=auth_headers(admin_token),
        )
        if retrieval_resp.status_code != 200:
            fail(f"admin rag retrieval logs failed: {retrieval_resp.status_code}\n{retrieval_resp.text}")
        retrieval_items = list(retrieval_resp.json().get("data") or [])
        if not any(str(item.get("conversation_id") or "") == conversation_id for item in retrieval_items):
            fail(f"expected retrieval log tied to target conversation: {retrieval_resp.text}")

        audit_resp = client.get(
            f"{V1}/admin/logs/audit",
            headers=auth_headers(admin_token),
        )
        if audit_resp.status_code != 200:
            fail(f"admin audit logs failed: {audit_resp.status_code}\n{audit_resp.text}")
        audit_items = list(audit_resp.json().get("data") or [])
        if not audit_items:
            fail(f"expected at least one audit item: {audit_resp.text}")

    print("ALL PASS: admin monitoring APIs are working.")


if __name__ == "__main__":
    main()
