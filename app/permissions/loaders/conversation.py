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


def load_company_member_active_or_403(
    *, session: Session, company_id: UUID, user_id: UUID
) -> CompanyMember:
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
    return m