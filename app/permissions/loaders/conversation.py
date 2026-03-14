from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from app.permissions.core import forbid, not_found
from app.conversation.model import Conversation
from app.company_member.model import CompanyMember
from app.common.enums import MemberStatus


def load_conversation_or_404(
    *, session: Session, conversation_id: UUID
) -> Conversation:
    c = session.get(Conversation, conversation_id)
    if not c:
        raise not_found("Conversation not found", field="conversation_id")
    return c


def load_rule_set_owner_active_or_403(
    *, session: Session, rule_set_id: UUID, user_id: UUID
) -> CompanyMember:
    stmt = (
        select(CompanyMember)
        .where(CompanyMember.company_id == rule_set_id)
        .where(CompanyMember.user_id == user_id)
        .where(CompanyMember.status == MemberStatus.active)
    )
    m = session.exec(stmt).first()
    if not m:
        raise forbid(
            "Rule set owner required",
            field="rule_set_id",
            reason="not_rule_set_owner",
        )
    return m


def load_company_member_active_or_403(
    *, session: Session, company_id: UUID, user_id: UUID
) -> CompanyMember:
    # Backward-compatible alias while legacy company_id call sites remain.
    return load_rule_set_owner_active_or_403(
        session=session,
        rule_set_id=company_id,
        user_id=user_id,
    )
