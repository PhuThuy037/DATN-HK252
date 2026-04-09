from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from app.auth import service as auth_service
from app.common.enums import MemberRole, MemberStatus, SystemRole
from app.common.error_codes import ErrorCode
from app.common.errors import AppError
from app.company.model import Company
from app.company_member.model import CompanyMember
from app.permissions.core import forbid, not_found
from app.permissions.loaders.conversation import load_company_member_active_or_403


def _load_company_or_404(*, session: Session, company_id: UUID) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise not_found("Rule set not found", field="rule_set_id")
    return company


def _load_active_membership(*, session: Session, user_id: UUID) -> CompanyMember | None:
    return session.exec(
        select(CompanyMember)
        .where(CompanyMember.user_id == user_id)
        .where(CompanyMember.status == MemberStatus.active)
        .order_by(CompanyMember.joined_at.desc())
        .limit(1)
    ).first()


def _is_system_admin(*, session: Session, user_id: UUID) -> bool:
    user = auth_service.get_user_by_id(session=session, user_id=user_id)
    return user.role == SystemRole.admin


def _require_rule_set_owner(
    *, session: Session, company_id: UUID, user_id: UUID
) -> CompanyMember | None:
    if _is_system_admin(session=session, user_id=user_id):
        return None

    member = load_company_member_active_or_403(
        session=session,
        company_id=company_id,
        user_id=user_id,
    )
    if member.role != MemberRole.company_admin:
        raise forbid(
            "Rule set owner required",
            field="rule_set_id",
            reason="not_rule_set_owner",
        )
    return member


def create_company(*, session: Session, user_id: UUID, name: str) -> tuple[Company, CompanyMember]:
    normalized_name = (name or "").strip()
    if not normalized_name:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Invalid rule set name",
            details=[{"field": "name", "reason": "empty_after_trim"}],
        )

    existing_membership = _load_active_membership(session=session, user_id=user_id)
    if existing_membership is not None:
        if existing_membership.role != MemberRole.company_admin:
            raise forbid(
                "Single-user mode requires owner role",
                field="user_id",
                reason="single_user_requires_owner",
            )
        raise AppError(
            409,
            ErrorCode.RULE_SET_ALREADY_EXISTS,
            "User already has an active personal rule set",
            details=[
                {
                    "field": "rule_set_id",
                    "reason": "already_exists",
                    "extra": {"existing_rule_set_id": str(existing_membership.company_id)},
                }
            ],
        )

    company = Company(name=normalized_name)
    session.add(company)
    session.flush()

    owner_member = CompanyMember(
        company_id=company.id,
        user_id=user_id,
        role=MemberRole.company_admin,
        status=MemberStatus.active,
    )
    session.add(owner_member)
    session.commit()
    session.refresh(company)
    session.refresh(owner_member)
    return company, owner_member


def list_my_companies(*, session: Session, user_id: UUID) -> list[tuple[Company, MemberRole]]:
    member = _load_active_membership(session=session, user_id=user_id)
    if member is None or member.role != MemberRole.company_admin:
        return []

    company = _load_company_or_404(session=session, company_id=member.company_id)
    return [(company, member.role)]


def get_company_for_member(
    *, session: Session, company_id: UUID, user_id: UUID
) -> tuple[Company, MemberRole]:
    company = _load_company_or_404(session=session, company_id=company_id)
    member = _require_rule_set_owner(
        session=session,
        company_id=company_id,
        user_id=user_id,
    )
    role = member.role if member is not None else MemberRole.company_admin
    return company, role


def add_member_by_email(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    email: str,
):
    raise forbid(
        "Members are disabled in single-user mode",
        field="rule_set_id",
        reason="members_disabled",
    )


def list_company_members(
    *, session: Session, company_id: UUID, actor_user_id: UUID
):
    raise forbid(
        "Members are disabled in single-user mode",
        field="rule_set_id",
        reason="members_disabled",
    )


def update_member(
    *,
    session: Session,
    company_id: UUID,
    member_id: UUID,
    actor_user_id: UUID,
    role: MemberRole | None,
    status: MemberStatus | None,
):
    raise forbid(
        "Members are disabled in single-user mode",
        field="rule_set_id",
        reason="members_disabled",
    )


def get_system_prompt(*, session: Session, company_id: UUID, user_id: UUID) -> Company:
    company = _load_company_or_404(session=session, company_id=company_id)
    _require_rule_set_owner(session=session, company_id=company_id, user_id=user_id)
    return company


def update_system_prompt(
    *,
    session: Session,
    company_id: UUID,
    user_id: UUID,
    system_prompt: str | None,
) -> Company:
    company = _load_company_or_404(session=session, company_id=company_id)
    _require_rule_set_owner(session=session, company_id=company_id, user_id=user_id)

    normalized = (system_prompt or "").strip()
    company.system_prompt = normalized or None
    session.add(company)
    session.commit()
    session.refresh(company)
    return company
