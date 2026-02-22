from __future__ import annotations

import hashlib
from uuid import UUID

from sqlmodel import Session, select

from app.conversation.model import Conversation
from app.messages.model import Message
from app.company_member.model import CompanyMember
from app.common.enums import MemberStatus, MessageRole, MessageInputType
from app.permissions.core import forbid, not_found


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
    """
    Append message to a conversation with safe sequence_number increment.

    Assumes access control already handled (Guard/Deps).
    Uses SELECT FOR UPDATE to avoid seq race.
    """
    # lock conversation row
    stmt = (
        select(Conversation).where(Conversation.id == conversation_id).with_for_update()
    )
    c = session.exec(stmt).first()
    if not c:
        raise not_found("Conversation not found", field="conversation_id")

    # Personal convo: owner-only
    if c.company_id is None and c.user_id != user_id:
        raise not_found(
            "Conversation not found", field="conversation_id", reason="not_owner"
        )

    # Company convo: membership check
    if c.company_id is not None:
        mem_stmt = (
            select(CompanyMember)
            .where(CompanyMember.company_id == c.company_id)
            .where(CompanyMember.user_id == user_id)
            .where(CompanyMember.status == MemberStatus.active)
        )
        mem = session.exec(mem_stmt).first()
        if not mem:
            # 404 để tránh leak
            raise not_found(
                "Conversation not found",
                field="conversation_id",
                reason="not_company_member",
            )

    # increment seq
    c.last_sequence_number = (c.last_sequence_number or 0) + 1
    seq = c.last_sequence_number

    msg = Message(
        conversation_id=c.id,
        role=MessageRole.user,
        sequence_number=seq,
        input_type=input_type,
        content=content,
        content_hash=_sha256_hex(content),
        # scan_status default pending theo model
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