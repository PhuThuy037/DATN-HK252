from __future__ import annotations

import hashlib
from uuid import UUID

from sqlmodel import Session, select

from app.conversation.model import Conversation
from app.messages.model import Message
from app.company_member.model import CompanyMember
from app.common.enums import MemberStatus, MessageRole, MessageInputType
from app.permissions.core import forbid, not_found
from app.decision.scan_engine_local import ScanEngineLocal
from app.decision.serializers import entity_to_dict, rulematch_to_dict
from app.common.enums import RuleAction, ScanStatus
import anyio
from app.masking.service import MaskService


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_scan = ScanEngineLocal(context_yaml_path="app/config/context_base.yaml")
_mask_service = MaskService()


def create_personal_conversation(
    *,
    session: Session,
    user_id: UUID,
    title: str | None = None,
    model_name: str | None = None,
    temperature: float | None = None,
) -> Conversation:
    c = Conversation(
        user_id=user_id,
        company_id=None,
        title=title,
        model_name=model_name,
        temperature=temperature,
        last_sequence_number=0,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def create_company_conversation(
    *,
    session: Session,
    user_id: UUID,
    company_id: UUID,
    title: str | None = None,
    model_name: str | None = None,
    temperature: float | None = None,
) -> Conversation:
    # require active membership
    stmt = (
        select(CompanyMember)
        .where(CompanyMember.company_id == company_id)
        .where(CompanyMember.user_id == user_id)
        .where(CompanyMember.status == MemberStatus.active)
    )
    m = session.exec(stmt).first()
    if not m:
        raise forbid(
            "Company membership required",
            field="company_id",
            reason="not_company_member",
        )

    c = Conversation(
        user_id=user_id,
        company_id=company_id,
        title=title,
        model_name=model_name,
        temperature=temperature,
        last_sequence_number=0,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def append_user_message(
    *,
    session: Session,
    conversation_id: UUID,
    user_id: UUID,
    content: str,
    input_type: MessageInputType = MessageInputType.user_input,
) -> Message:

    stmt = (
        select(Conversation).where(Conversation.id == conversation_id).with_for_update()
    )
    c = session.exec(stmt).first()
    if not c:
        raise not_found("Conversation not found", field="conversation_id")

    if c.company_id is None and c.user_id != user_id:
        raise not_found(
            "Conversation not found", field="conversation_id", reason="not_owner"
        )

    if c.company_id is not None:
        mem_stmt = (
            select(CompanyMember)
            .where(CompanyMember.company_id == c.company_id)
            .where(CompanyMember.user_id == user_id)
            .where(CompanyMember.status == MemberStatus.active)
        )
        mem = session.exec(mem_stmt).first()
        if not mem:
            raise not_found(
                "Conversation not found",
                field="conversation_id",
                reason="not_company_member",
            )

    c.last_sequence_number = (c.last_sequence_number or 0) + 1
    seq = c.last_sequence_number

    # -------- SCAN --------
    scan = anyio.run(
        lambda: _scan.scan(
            session=session,
            text=content,
            company_id=c.company_id,
        )
    )

    final_action: RuleAction = scan["final_action"]
    entities = scan["entities"]
    matches = scan["matches"]

    # -------- MASK LOGIC --------
    blocked = final_action == RuleAction.block

    if final_action == RuleAction.mask:
        masked_content = _mask_service.mask(content, entities)
    else:
        masked_content = None

    entities_json = {
        "entities": [entity_to_dict(e) for e in entities],
        "signals": scan["signals"],
        "matched_rules": [rulematch_to_dict(m) for m in matches],
    }

    matched_rule_ids = [str(m.rule_id) for m in matches]

    msg = Message(
        conversation_id=c.id,
        role=MessageRole.user,
        sequence_number=seq,
        input_type=input_type,
        content=None if blocked else content,
        content_hash=_sha256_hex(content),
        content_masked=masked_content,
        scan_status=ScanStatus.done,
        pre_rag_action=None,
        final_action=final_action,
        risk_score=scan["risk_score"],
        ambiguous=scan["ambiguous"],
        matched_rule_ids=matched_rule_ids,
        entities_json=entities_json,
        rag_evidence_json=None,
        latency_ms=scan["latency_ms"],
    )

    session.add(msg)
    session.add(c)
    session.commit()
    session.refresh(msg)

    return msg


def list_messages(
    *,
    session: Session,
    conversation_id: UUID,
) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence_number.asc())
    )
    return list(session.exec(stmt).all())