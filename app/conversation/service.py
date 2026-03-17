# app/conversation/service.py
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from uuid import UUID

import anyio
import sqlalchemy as sa
from sqlmodel import Session, select

from app.chat.service import ChatService
from app.common.error_codes import ErrorCode
from app.common.errors import AppError
from app.common.enums import (
    ConversationStatus,
    MessageInputType,
    MessageRole,
    RuleAction,
    ScanStatus,
)
from app.company.model import Company
from app.conversation.model import Conversation
from app.core.config import get_settings
from app.decision.scan_engine_local import ScanEngineLocal
from app.decision.serializers import entity_to_dict, rulematch_to_dict
from app.masking.service import MaskService
from app.messages.model import Message
from app.permissions.core import not_found
from app.permissions.loaders.conversation import load_rule_set_owner_active_or_403

_chat = ChatService()
_scan = ScanEngineLocal(context_yaml_path="app/config/context_base.yaml")
_mask_service = MaskService()
_settings = get_settings()
_CODE_LIKE_TERM_RE = re.compile(r"[A-Za-z0-9]{2,}(?:[-_][A-Za-z0-9]{1,}){1,}")


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_message_content(message: Message) -> tuple[str | None, bool]:
    is_blocked = message.final_action == RuleAction.block
    is_masked = message.final_action == RuleAction.mask

    if is_blocked:
        return None, True
    if message.content_masked is not None:
        return message.content_masked, False
    if is_masked:
        return None, False
    return message.content, False


def _truncate_preview(text: str | None, *, max_length: int = 180) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    if len(value) <= max_length:
        return value
    return f"{value[:max_length].rstrip()}..."


def _extract_code_like_mask_terms(scan_payload: dict) -> list[str]:
    signals = scan_payload.get("signals") if isinstance(scan_payload, dict) else None
    if not isinstance(signals, dict):
        return []
    context_keywords = signals.get("context_keywords")
    if not isinstance(context_keywords, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in context_keywords:
        term = str(value or "").strip()
        if not term:
            continue
        if _CODE_LIKE_TERM_RE.search(term) is None:
            continue
        lowered = term.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(term)
    return out


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


def create_rule_set_conversation(
    *,
    session: Session,
    user_id: UUID,
    rule_set_id: UUID,
    title: str | None = None,
    model_name: str | None = None,
    temperature: float | None = None,
) -> Conversation:
    load_rule_set_owner_active_or_403(
        session=session,
        rule_set_id=rule_set_id,
        user_id=user_id,
    )

    c = Conversation(
        user_id=user_id,
        company_id=rule_set_id,
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
    # Backward-compatible alias while legacy call sites still pass company_id.
    return create_rule_set_conversation(
        session=session,
        user_id=user_id,
        rule_set_id=company_id,
        title=title,
        model_name=model_name,
        temperature=temperature,
    )


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
        try:
            load_rule_set_owner_active_or_403(
                session=session,
                rule_set_id=c.company_id,
                user_id=user_id,
            )
        except AppError:
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
        user_masked = _mask_service.mask(
            content,
            user_entities,
            extra_terms=_extract_code_like_mask_terms(user_scan),
        )

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
        asst_masked = _mask_service.mask(
            assistant_text,
            asst_entities,
            extra_terms=_extract_code_like_mask_terms(assistant_scan),
        )

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


def list_conversations_page(
    *,
    session: Session,
    user_id: UUID,
    limit: int,
    before_updated_at: datetime | None = None,
    before_id: UUID | None = None,
    status: ConversationStatus | None = ConversationStatus.active,
) -> tuple[list[Conversation], bool, datetime | None, UUID | None]:
    safe_limit = max(1, min(int(limit), 50))
    stmt = select(Conversation).where(Conversation.user_id == user_id)

    if status is not None:
        stmt = stmt.where(Conversation.status == status)

    if before_updated_at is not None:
        if before_id is not None:
            stmt = stmt.where(
                sa.or_(
                    Conversation.updated_at < before_updated_at,
                    sa.and_(
                        Conversation.updated_at == before_updated_at,
                        Conversation.id < before_id,
                    ),
                )
            )
        else:
            stmt = stmt.where(Conversation.updated_at < before_updated_at)

    stmt = stmt.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(
        safe_limit + 1
    )
    rows = list(session.exec(stmt).all())

    has_more = len(rows) > safe_limit
    if has_more:
        rows = rows[:safe_limit]

    next_before_updated_at = rows[-1].updated_at if (rows and has_more) else None
    next_before_id = rows[-1].id if (rows and has_more) else None
    return rows, has_more, next_before_updated_at, next_before_id


def get_conversation_or_404(*, session: Session, conversation_id: UUID) -> Conversation:
    row = session.get(Conversation, conversation_id)
    if not row:
        raise not_found("Conversation not found", field="conversation_id")
    return row


def get_last_message_summary(
    *, session: Session, conversation_id: UUID
) -> tuple[datetime | None, str | None]:
    row = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence_number.desc())
        .limit(1)
    ).first()
    if row is None:
        return None, None

    safe_content, _ = _safe_message_content(row)
    return row.created_at, _truncate_preview(safe_content)


def get_message_for_conversation_or_404(
    *,
    session: Session,
    conversation_id: UUID,
    message_id: UUID,
) -> Message:
    row = session.get(Message, message_id)
    if row is None or row.conversation_id != conversation_id:
        raise not_found("Message not found", field="message_id")
    return row


def build_safe_message_detail(*, message: Message) -> dict:
    safe_content, is_blocked = _safe_message_content(message)
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "role": message.role,
        "sequence_number": message.sequence_number,
        "input_type": message.input_type,
        "content": safe_content,
        "content_masked": message.content_masked,
        "scan_status": (
            message.scan_status.value
            if hasattr(message.scan_status, "value")
            else str(message.scan_status)
        ),
        "final_action": (
            message.final_action.value
            if hasattr(message.final_action, "value")
            else (
                str(message.final_action)
                if message.final_action is not None
                else None
            )
        ),
        "risk_score": message.risk_score,
        "ambiguous": bool(message.ambiguous),
        "matched_rule_ids": message.matched_rule_ids,
        "entities_json": message.entities_json,
        "rag_evidence_json": message.rag_evidence_json,
        "latency_ms": message.latency_ms,
        "blocked": is_blocked,
        "blocked_reason": getattr(message, "blocked_reason", None),
        "created_at": message.created_at,
    }


def update_conversation_metadata(
    *,
    session: Session,
    conversation_id: UUID,
    title: str | None,
    status: ConversationStatus | None,
    fields_set: set[str],
) -> Conversation:
    row = get_conversation_or_404(session=session, conversation_id=conversation_id)

    if not fields_set:
        return row

    if "title" in fields_set:
        normalized = (title or "").strip()
        row.title = normalized or None

    if "status" in fields_set:
        if status is None:
            raise AppError(
                422,
                ErrorCode.VALIDATION_ERROR,
                "Invalid status",
                details=[{"field": "status", "reason": "required"}],
            )
        row.status = status

    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def soft_delete_conversation(
    *,
    session: Session,
    conversation_id: UUID,
) -> Conversation:
    row = get_conversation_or_404(session=session, conversation_id=conversation_id)
    if row.status != ConversationStatus.archived:
        row.status = ConversationStatus.archived
        session.add(row)
        session.commit()
        session.refresh(row)
    return row
