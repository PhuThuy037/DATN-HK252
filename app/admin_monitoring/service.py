from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Session, select

from app.admin_monitoring.schemas import (
    AdminAuditLogOut,
    AdminBlockMaskLogOut,
    AdminConversationDetailOut,
    AdminConversationListItemOut,
    AdminRagRetrievalLogOut,
)
from app.auth.model import User
from app.common.enums import ConversationStatus, RuleAction
from app.conversation import service as conversation_service
from app.conversation.model import Conversation
from app.messages.model import Message
from app.permissions.core import not_found
from app.rag.models.rag_retrieval_log import RagRetrievalLog
from app.rule_change_log.model import RuleChangeLog


def _normalize_limit(*, limit: int, maximum: int = 100) -> int:
    return max(1, min(int(limit), maximum))


def _decode_offset_cursor(*, cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        value = int(str(cursor).strip() or "0")
    except ValueError:
        return 0
    return max(0, value)


def _encode_offset_cursor(*, offset: int, limit: int, has_more: bool) -> str | None:
    if not has_more:
        return None
    return str(offset + limit)


def _action_value(value: RuleAction | str | None) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _status_value(value: ConversationStatus | str) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _message_summary(detail: dict) -> str | None:
    matched_rules = detail.get("matched_rules") if isinstance(detail, dict) else None
    if isinstance(matched_rules, list):
        names = [
            str(row.get("name") or row.get("stable_key") or "").strip()
            for row in matched_rules
            if isinstance(row, dict)
        ]
        names = [name for name in names if name]
        if names:
            head = ", ".join(names[:2])
            if len(names) > 2:
                return f"{head} +{len(names) - 2} more"
            return head

    if detail.get("blocked"):
        blocked_reason = str(detail.get("blocked_reason") or "").strip()
        if blocked_reason:
            return blocked_reason
        return "Blocked by policy"

    final_action = str(detail.get("final_action") or "").strip().lower()
    if final_action == "mask":
        return "Masked by policy"
    if final_action == "block":
        return "Blocked by policy"
    return None


def _conversation_stats_subquery():
    block_case = sa.case((Message.final_action == RuleAction.block, 1), else_=0)
    mask_case = sa.case((Message.final_action == RuleAction.mask, 1), else_=0)
    return (
        select(
            Message.conversation_id.label("conversation_id"),
            sa.func.count(Message.id).label("message_count"),
            sa.func.coalesce(sa.func.sum(block_case), 0).label("block_count"),
            sa.func.coalesce(sa.func.sum(mask_case), 0).label("mask_count"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )


def list_admin_conversations_paginated(
    *,
    session: Session,
    limit: int,
    cursor: str | None = None,
    status: ConversationStatus | None = None,
    q: str | None = None,
) -> tuple[list[AdminConversationListItemOut], str | None, bool, int]:
    safe_limit = _normalize_limit(limit=limit)
    offset = _decode_offset_cursor(cursor=cursor)
    stats_sq = _conversation_stats_subquery()

    stmt = (
        select(
            Conversation,
            User,
            stats_sq.c.message_count,
            stats_sq.c.block_count,
            stats_sq.c.mask_count,
        )
        .join(User, User.id == Conversation.user_id)
        .outerjoin(stats_sq, stats_sq.c.conversation_id == Conversation.id)
    )

    count_stmt = select(sa.func.count()).select_from(Conversation).join(
        User, User.id == Conversation.user_id
    )

    if status is not None:
        stmt = stmt.where(Conversation.status == status)
        count_stmt = count_stmt.where(Conversation.status == status)

    search = str(q or "").strip()
    if search:
        like = f"%{search}%"
        search_clause = sa.or_(
            Conversation.title.ilike(like),
            User.email.ilike(like),
            User.name.ilike(like),
            sa.cast(Conversation.id, sa.String).ilike(like),
            sa.cast(Conversation.user_id, sa.String).ilike(like),
        )
        stmt = stmt.where(search_clause)
        count_stmt = count_stmt.where(search_clause)

    stmt = stmt.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).offset(
        offset
    ).limit(safe_limit + 1)

    rows = list(session.exec(stmt).all())
    has_more = len(rows) > safe_limit
    if has_more:
        rows = rows[:safe_limit]

    total = int(session.exec(count_stmt).one())
    items: list[AdminConversationListItemOut] = []
    for convo, owner, message_count, block_count, mask_count in rows:
        last_message_at, last_message_preview = (
            conversation_service.get_admin_last_message_summary(
            session=session,
            conversation_id=convo.id,
        )
        )
        block_total = int(block_count or 0)
        mask_total = int(mask_count or 0)
        items.append(
            AdminConversationListItemOut(
                id=convo.id,
                user_id=owner.id,
                user_email=owner.email,
                user_name=owner.name,
                rule_set_id=convo.company_id,
                title=convo.title,
                status=_status_value(convo.status),
                model_name=convo.model_name,
                temperature=convo.temperature,
                last_sequence_number=convo.last_sequence_number,
                created_at=convo.created_at,
                updated_at=convo.updated_at,
                last_message_at=last_message_at,
                last_message_preview=last_message_preview,
                message_count=int(message_count or 0),
                block_count=block_total,
                mask_count=int(mask_total),
                has_sensitive_action=(block_total + int(mask_total)) > 0,
            )
        )

    next_cursor = _encode_offset_cursor(
        offset=offset,
        limit=safe_limit,
        has_more=has_more,
    )
    return items, next_cursor, has_more, total


def get_admin_conversation_detail(
    *,
    session: Session,
    conversation_id: UUID,
) -> AdminConversationDetailOut:
    stats_sq = _conversation_stats_subquery()
    stmt = (
        select(
            Conversation,
            User,
            stats_sq.c.message_count,
            stats_sq.c.block_count,
            stats_sq.c.mask_count,
        )
        .join(User, User.id == Conversation.user_id)
        .outerjoin(stats_sq, stats_sq.c.conversation_id == Conversation.id)
        .where(Conversation.id == conversation_id)
    )
    row = session.exec(stmt).first()
    if not row:
        raise not_found("Conversation not found", field="conversation_id")

    convo, owner, message_count, block_count, mask_count = row
    return AdminConversationDetailOut(
        id=convo.id,
        user_id=owner.id,
        user_email=owner.email,
        user_name=owner.name,
        rule_set_id=convo.company_id,
        title=convo.title,
        status=_status_value(convo.status),
        model_name=convo.model_name,
        temperature=convo.temperature,
        last_sequence_number=convo.last_sequence_number,
        created_at=convo.created_at,
        updated_at=convo.updated_at,
        message_count=int(message_count or 0),
        block_count=int(block_count or 0),
        mask_count=int(mask_count or 0),
    )


def list_admin_conversation_messages_page(
    *,
    session: Session,
    conversation_id: UUID,
    limit: int,
    before_seq: int | None = None,
):
    conversation_service.get_conversation_or_404(
        session=session,
        conversation_id=conversation_id,
    )
    safe_limit = _normalize_limit(limit=limit)
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    if before_seq is not None:
        stmt = stmt.where(Message.sequence_number < before_seq)

    stmt = stmt.order_by(Message.sequence_number.desc()).limit(safe_limit + 1)
    rows_desc = list(session.exec(stmt).all())
    has_more = len(rows_desc) > safe_limit
    if has_more:
        rows_desc = rows_desc[:safe_limit]

    rows = list(reversed(rows_desc))
    oldest_seq = rows[0].sequence_number if rows else None
    newest_seq = rows[-1].sequence_number if rows else None
    next_before_seq = oldest_seq if has_more else None
    items = [
        conversation_service.build_admin_message_detail(message=row) for row in rows
    ]
    return items, has_more, next_before_seq, oldest_seq, newest_seq


def list_admin_block_mask_logs_paginated(
    *,
    session: Session,
    limit: int,
    cursor: str | None = None,
    action: str | None = None,
) -> tuple[list[AdminBlockMaskLogOut], str | None, bool, int]:
    safe_limit = _normalize_limit(limit=limit)
    offset = _decode_offset_cursor(cursor=cursor)
    actions: list[RuleAction] = [RuleAction.block, RuleAction.mask]
    normalized_action = str(action or "").strip().lower()
    if normalized_action == "block":
        actions = [RuleAction.block]
    elif normalized_action == "mask":
        actions = [RuleAction.mask]

    base_stmt = (
        select(Message, Conversation, User)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .join(User, User.id == Conversation.user_id)
        .where(Message.final_action.in_(actions))
    )

    stmt = (
        base_stmt.order_by(Message.created_at.desc(), Message.id.desc())
        .offset(offset)
        .limit(safe_limit + 1)
    )
    rows = list(session.exec(stmt).all())
    has_more = len(rows) > safe_limit
    if has_more:
        rows = rows[:safe_limit]

    total = int(
        session.exec(
            select(sa.func.count())
            .select_from(Message)
            .where(Message.final_action.in_(actions))
        ).one()
    )

    items: list[AdminBlockMaskLogOut] = []
    for message, convo, owner in rows:
        detail = conversation_service.build_admin_message_detail(message=message)
        items.append(
            AdminBlockMaskLogOut(
                message_id=message.id,
                conversation_id=convo.id,
                user_id=owner.id,
                user_email=owner.email,
                user_name=owner.name,
                conversation_title=convo.title,
                role=(
                    message.role.value
                    if hasattr(message.role, "value")
                    else str(message.role)
                ),
                input_type=(
                    message.input_type.value
                    if hasattr(message.input_type, "value")
                    else str(message.input_type)
                )
                if message.input_type is not None
                else None,
                action=_action_value(message.final_action) or "unknown",
                summary=_message_summary(detail),
                content=detail.get("content"),
                content_masked=detail.get("content_masked"),
                matched_rule_ids=detail.get("matched_rule_ids"),
                matched_rules=detail.get("matched_rules"),
                risk_score=detail.get("risk_score"),
                blocked=bool(detail.get("blocked")),
                created_at=message.created_at,
            )
        )

    next_cursor = _encode_offset_cursor(
        offset=offset,
        limit=safe_limit,
        has_more=has_more,
    )
    return items, next_cursor, has_more, total


def list_admin_rag_retrieval_logs_paginated(
    *,
    session: Session,
    limit: int,
    cursor: str | None = None,
) -> tuple[list[AdminRagRetrievalLogOut], str | None, bool, int]:
    safe_limit = _normalize_limit(limit=limit)
    offset = _decode_offset_cursor(cursor=cursor)

    stmt = (
        select(RagRetrievalLog, Message, Conversation, User)
        .outerjoin(Message, Message.id == RagRetrievalLog.message_id)
        .outerjoin(Conversation, Conversation.id == Message.conversation_id)
        .outerjoin(User, User.id == Conversation.user_id)
        .order_by(RagRetrievalLog.created_at.desc(), RagRetrievalLog.id.desc())
        .offset(offset)
        .limit(safe_limit + 1)
    )
    rows = list(session.exec(stmt).all())
    has_more = len(rows) > safe_limit
    if has_more:
        rows = rows[:safe_limit]

    total = int(
        session.exec(select(sa.func.count()).select_from(RagRetrievalLog)).one()
    )

    items: list[AdminRagRetrievalLogOut] = []
    for log_row, message, convo, owner in rows:
        results_json = (
            log_row.results_json if isinstance(log_row.results_json, dict) else {}
        )
        raw_results = results_json.get("results")
        if isinstance(raw_results, list):
            result_count = len(raw_results)
        elif isinstance(results_json, list):
            result_count = len(results_json)
        else:
            result_count = 0

        items.append(
            AdminRagRetrievalLogOut(
                id=log_row.id,
                message_id=log_row.message_id,
                conversation_id=convo.id if convo else None,
                user_id=owner.id if owner else None,
                user_email=owner.email if owner else None,
                user_name=owner.name if owner else None,
                query=log_row.query,
                top_k=log_row.top_k,
                result_count=result_count,
                latency_ms=log_row.latency_ms,
                created_at=log_row.created_at,
            )
        )

    next_cursor = _encode_offset_cursor(
        offset=offset,
        limit=safe_limit,
        has_more=has_more,
    )
    return items, next_cursor, has_more, total


def list_admin_audit_logs_paginated(
    *,
    session: Session,
    limit: int,
    cursor: str | None = None,
) -> tuple[list[AdminAuditLogOut], str | None, bool, int]:
    safe_limit = _normalize_limit(limit=limit)
    offset = _decode_offset_cursor(cursor=cursor)

    stmt = (
        select(RuleChangeLog, User)
        .outerjoin(User, User.id == RuleChangeLog.actor_user_id)
        .order_by(RuleChangeLog.created_at.desc(), RuleChangeLog.id.desc())
        .offset(offset)
        .limit(safe_limit + 1)
    )
    rows = list(session.exec(stmt).all())
    has_more = len(rows) > safe_limit
    if has_more:
        rows = rows[:safe_limit]

    total = int(
        session.exec(select(sa.func.count()).select_from(RuleChangeLog)).one()
    )

    items: list[AdminAuditLogOut] = []
    for row, actor in rows:
        items.append(
            AdminAuditLogOut(
                id=row.id,
                rule_set_id=row.company_id,
                rule_id=row.rule_id,
                actor_user_id=row.actor_user_id,
                actor_email=actor.email if actor else None,
                actor_name=actor.name if actor else None,
                action=row.action,
                changed_fields=list(row.changed_fields or []),
                before_json=row.before_json,
                after_json=row.after_json,
                created_at=row.created_at,
            )
        )

    next_cursor = _encode_offset_cursor(
        offset=offset,
        limit=safe_limit,
        has_more=has_more,
    )
    return items, next_cursor, has_more, total
