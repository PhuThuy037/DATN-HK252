# app/conversation/service.py
from __future__ import annotations

import hashlib
from uuid import UUID

import anyio
from sqlmodel import Session, select

from app.chat.service import ChatService
from app.common.enums import (
    MemberRole,
    MemberStatus,
    MessageInputType,
    MessageRole,
    RuleAction,
    ScanStatus,
)
from app.company.model import Company
from app.company_member.model import CompanyMember
from app.conversation.model import Conversation
from app.core.config import get_settings
from app.decision.scan_engine_local import ScanEngineLocal
from app.decision.serializers import entity_to_dict, rulematch_to_dict
from app.masking.service import MaskService
from app.messages.model import Message
from app.permissions.core import forbid, not_found

_chat = ChatService()
_scan = ScanEngineLocal(context_yaml_path="app/config/context_base.yaml")
_mask_service = MaskService()
_settings = get_settings()


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_system_prompt(
    *, session: Session, conversation: Conversation
) -> str | None:
    if conversation.company_id:
        company = session.get(Company, conversation.company_id)
        company_prompt = (company.system_prompt or "").strip() if company else ""
        if company_prompt:
            return company_prompt

    default_prompt = (_settings.default_system_prompt or "").strip()
    return default_prompt or None


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
    stmt = (
        select(CompanyMember)
        .where(CompanyMember.company_id == company_id)
        .where(CompanyMember.user_id == user_id)
        .where(CompanyMember.status == MemberStatus.active)
    )
    m = session.exec(stmt).first()
    if not m or m.role != MemberRole.company_admin:
        raise forbid(
            "Rule set owner required",
            field="rule_set_id",
            reason="not_rule_set_owner",
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


async def append_user_message_async(
    *,
    session: Session,
    conversation_id: UUID,
    user_id: UUID,
    content: str,
    input_type: MessageInputType = MessageInputType.user_input,
) -> tuple[Message, UUID | None]:
    """
    Async flow:
      1) Save USER message (scan + mask/block)
      2) Call ChatService
      3) Save ASSISTANT message (scan + mask/block)
    Return: (user_msg, assistant_message_id)
    """
    stmt = (
        select(Conversation).where(Conversation.id == conversation_id).with_for_update()
    )
    c = session.exec(stmt).first()
    if not c:
        raise not_found("Conversation not found", field="conversation_id")

    if c.company_id is None and c.user_id != user_id:
        raise not_found(
            "Conversation not found",
            field="conversation_id",
            reason="not_owner",
        )

    if c.company_id is not None:
        mem_stmt = (
            select(CompanyMember)
            .where(CompanyMember.company_id == c.company_id)
            .where(CompanyMember.user_id == user_id)
            .where(CompanyMember.status == MemberStatus.active)
        )
        mem = session.exec(mem_stmt).first()
        if not mem or mem.role != MemberRole.company_admin:
            raise not_found(
                "Conversation not found",
                field="conversation_id",
                reason="not_rule_set_owner",
            )

    # STEP 1: user message
    c.last_sequence_number = (c.last_sequence_number or 0) + 1
    user_seq = c.last_sequence_number

    user_scan = await _scan.scan(
        session=session,
        text=content,
        company_id=c.company_id,
        user_id=user_id,
    )

    user_final: RuleAction = user_scan["final_action"]
    user_entities = user_scan["entities"]
    user_matches = user_scan["matches"]

    user_blocked = user_final == RuleAction.block

    user_masked = None
    if user_final == RuleAction.mask:
        user_masked = _mask_service.mask(content, user_entities)

    user_entities_json = {
        "entities": [entity_to_dict(e) for e in user_entities],
        "signals": user_scan["signals"],
        "matched_rules": [rulematch_to_dict(m) for m in user_matches],
        "timing_ms_by_stage": user_scan.get("timing_ms_by_stage") or {},
    }
    user_matched_rule_ids = [str(m.rule_id) for m in user_matches]

    user_msg = Message(
        conversation_id=c.id,
        role=MessageRole.user,
        sequence_number=user_seq,
        input_type=input_type,
        content=None if user_blocked else content,
        content_hash=_sha256_hex(content),
        content_masked=user_masked,
        scan_status=ScanStatus.done,
        pre_rag_action=None,
        final_action=user_final,
        risk_score=user_scan["risk_score"],
        ambiguous=user_scan["ambiguous"],
        matched_rule_ids=user_matched_rule_ids,
        entities_json=user_entities_json,
        rag_evidence_json=None,
        latency_ms=user_scan["latency_ms"],
    )

    session.add(user_msg)
    session.add(c)
    session.commit()
    session.refresh(user_msg)

    if user_blocked:
        return user_msg, None

    # STEP 2: call chat provider
    llm_input = user_masked or content
    system_prompt = _resolve_system_prompt(session=session, conversation=c)
    temperature = float(c.temperature or 0.7)
    model_name = c.model_name

    assistant_text = await _chat.generate_reply(
        system_prompt=system_prompt,
        user_message=llm_input,
        temperature=temperature,
        model_name=model_name,
    )

    assistant_scan = await _scan.scan(
        session=session,
        text=assistant_text,
        company_id=c.company_id,
        user_id=user_id,
    )

    # STEP 3: assistant message
    c.last_sequence_number = (c.last_sequence_number or 0) + 1
    asst_seq = c.last_sequence_number

    asst_final: RuleAction = assistant_scan["final_action"]
    asst_entities = assistant_scan["entities"]
    asst_matches = assistant_scan["matches"]

    asst_blocked = asst_final == RuleAction.block

    asst_masked = None
    if asst_final == RuleAction.mask:
        asst_masked = _mask_service.mask(assistant_text, asst_entities)

    asst_entities_json = {
        "entities": [entity_to_dict(e) for e in asst_entities],
        "signals": assistant_scan["signals"],
        "matched_rules": [rulematch_to_dict(m) for m in asst_matches],
        "timing_ms_by_stage": assistant_scan.get("timing_ms_by_stage") or {},
    }
    asst_matched_rule_ids = [str(m.rule_id) for m in asst_matches]

    assistant_msg = Message(
        conversation_id=c.id,
        role=MessageRole.assistant,
        sequence_number=asst_seq,
        input_type=MessageInputType.tool_result,
        content=None if asst_blocked else assistant_text,
        content_hash=_sha256_hex(assistant_text),
        content_masked=asst_masked,
        scan_status=ScanStatus.done,
        pre_rag_action=None,
        final_action=asst_final,
        risk_score=assistant_scan["risk_score"],
        ambiguous=assistant_scan["ambiguous"],
        matched_rule_ids=asst_matched_rule_ids,
        entities_json=asst_entities_json,
        rag_evidence_json=None,
        latency_ms=assistant_scan["latency_ms"],
    )

    session.add(assistant_msg)
    session.add(c)
    session.commit()
    session.refresh(assistant_msg)

    return user_msg, assistant_msg.id


def append_user_message(
    *,
    session: Session,
    conversation_id: UUID,
    user_id: UUID,
    content: str,
    input_type: MessageInputType = MessageInputType.user_input,
) -> Message:
    user_msg, _ = anyio.run(
        append_user_message_async,
        session=session,
        conversation_id=conversation_id,
        user_id=user_id,
        content=content,
        input_type=input_type,
    )
    return user_msg


def list_messages(*, session: Session, conversation_id: UUID) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence_number.asc())
    )
    return list(session.exec(stmt).all())


def list_messages_page(
    *,
    session: Session,
    conversation_id: UUID,
    limit: int,
    before_seq: int | None = None,
) -> tuple[list[Message], bool, int | None, int | None, int | None]:
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    if before_seq is not None:
        stmt = stmt.where(Message.sequence_number < before_seq)

    stmt = stmt.order_by(Message.sequence_number.desc()).limit(limit + 1)
    rows_desc = list(session.exec(stmt).all())

    has_more = len(rows_desc) > limit
    if has_more:
        rows_desc = rows_desc[:limit]

    rows = list(reversed(rows_desc))
    oldest_seq = rows[0].sequence_number if rows else None
    newest_seq = rows[-1].sequence_number if rows else None
    next_before_seq = oldest_seq if has_more else None

    return rows, has_more, next_before_seq, oldest_seq, newest_seq
