# app/conversation/service.py
from __future__ import annotations

import hashlib
from uuid import UUID

import anyio
from sqlmodel import Session, select

from app.chat.service import ChatService
from app.common.enums import (
    MemberStatus,
    MessageInputType,
    MessageRole,
    RuleAction,
    ScanStatus,
)
from app.company_member.model import CompanyMember
from app.conversation.model import Conversation
from app.decision.rule_layering import compact_matches
from app.decision.scan_engine_local import ScanEngineLocal
from app.decision.serializers import entity_to_dict, rulematch_to_dict
from app.masking.service import MaskService
from app.messages.model import Message
from app.permissions.core import forbid, not_found

_chat = ChatService()
_scan = ScanEngineLocal(context_yaml_path="app/config/context_base.yaml")
_mask_service = MaskService()


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =========================================================
# Conversation create APIs NEED these 2 functions
# =========================================================


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


# =========================================================
# Messages
# =========================================================


async def append_user_message_async(
    *,
    session: Session,
    conversation_id: UUID,
    user_id: UUID,
    content: str,
    input_type: MessageInputType = MessageInputType.user_input,
) -> Message:
    """
    Async version: dùng cho FastAPI async route (khuyến nghị).
    Flow:
      1) Save USER message (scan + mask/block)
      2) Call ChatService (dynamic model)
      3) Save ASSISTANT message (scan + mask/block)
    Return: user_msg (giữ nguyên contract)
    """
    stmt = (
        select(Conversation).where(Conversation.id == conversation_id).with_for_update()
    )
    c = session.exec(stmt).first()
    if not c:
        raise not_found("Conversation not found", field="conversation_id")

    # personal convo owner check
    if c.company_id is None and c.user_id != user_id:
        raise not_found(
            "Conversation not found",
            field="conversation_id",
            reason="not_owner",
        )

    # company convo membership check
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

    # -----------------------------
    # STEP 1) Save USER message
    # -----------------------------
    c.last_sequence_number = (c.last_sequence_number or 0) + 1
    user_seq = c.last_sequence_number

    user_scan = await _scan.scan(session=session, text=content, company_id=c.company_id)

    user_final: RuleAction = user_scan["final_action"]
    user_entities = user_scan["entities"]
    user_matches = compact_matches(
        user_scan["matches"], final_action=str(user_final).lower()
    )

    user_blocked = user_final == RuleAction.block

    user_masked = None
    if user_final == RuleAction.mask:
        user_masked = _mask_service.mask(content, user_entities)

    user_entities_json = {
        "entities": [entity_to_dict(e) for e in user_entities],
        "signals": user_scan["signals"],
        "matched_rules": [rulematch_to_dict(m) for m in user_matches],
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

    # Nếu user bị BLOCK -> stop luôn, KHÔNG gọi LLM
    if user_blocked:
        return user_msg

    # -----------------------------
    # STEP 2) Call ChatService (DYNAMIC MODEL HERE)
    # NOTE: gửi masked vào LLM nếu có (tránh leak)
    # -----------------------------
    llm_input = user_masked or content
    system_prompt = None
    temperature = float(c.temperature or 0.7)
    model_name = c.model_name  # "gemini-3-flash-preview" hoặc "qwen2.5:7b"

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
    )

    # -----------------------------
    # STEP 3) Save ASSISTANT message (scan + mask/block)
    # -----------------------------
    c.last_sequence_number = (c.last_sequence_number or 0) + 1
    asst_seq = c.last_sequence_number

    asst_final: RuleAction = assistant_scan["final_action"]
    asst_entities = assistant_scan["entities"]
    asst_matches = compact_matches(
        assistant_scan["matches"], final_action=str(asst_final).lower()
    )

    asst_blocked = asst_final == RuleAction.block

    asst_masked = None
    if asst_final == RuleAction.mask:
        asst_masked = _mask_service.mask(assistant_text, asst_entities)

    asst_entities_json = {
        "entities": [entity_to_dict(e) for e in asst_entities],
        "signals": assistant_scan["signals"],
        "matched_rules": [rulematch_to_dict(m) for m in asst_matches],
    }
    asst_matched_rule_ids = [str(m.rule_id) for m in asst_matches]

    assistant_msg = Message(
        conversation_id=c.id,
        role=MessageRole.assistant,
        sequence_number=asst_seq,
        input_type=MessageInputType.assistant_output,
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

    # giữ nguyên contract: return user_msg
    return user_msg


def append_user_message(
    *,
    session: Session,
    conversation_id: UUID,
    user_id: UUID,
    content: str,
    input_type: MessageInputType = MessageInputType.user_input,
) -> Message:
    """
    Sync wrapper: chỉ dùng cho script/CLI hoặc chỗ nào chắc chắn KHÔNG đang ở event loop.
    FastAPI async route -> gọi append_user_message_async() trực tiếp.
    """
    return anyio.run(
        append_user_message_async,
        session=session,
        conversation_id=conversation_id,
        user_id=user_id,
        content=content,
        input_type=input_type,
    )


def list_messages(*, session: Session, conversation_id: UUID) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence_number.asc())
    )
    return list(session.exec(stmt).all())