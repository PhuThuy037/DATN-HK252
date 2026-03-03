from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.model import User
from app.common.enums import MemberRole, MemberStatus, UserStatus
from app.common.error_codes import ErrorCode
from app.common.errors import AppError
from app.company.model import Company
from app.company_member.model import CompanyMember
from app.permissions.core import forbid, not_found
from app.permissions.loaders.conversation import load_company_member_active_or_403


def _load_company_or_404(*, session: Session, company_id: UUID) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise not_found("Company not found", field="company_id")
    return company


def _require_company_admin(*, session: Session, company_id: UUID, user_id: UUID) -> None:
    member = load_company_member_active_or_403(
        session=session, company_id=company_id, user_id=user_id
    )
    if member.role != MemberRole.company_admin:
        raise forbid(
            "Company admin required",
            field="company_id",
            reason="not_company_admin",
        )


def _load_user_by_email_or_404(*, session: Session, email: str) -> User:
    normalized = str(email).strip().lower()
    stmt = select(User).where(func.lower(User.email) == normalized)
    user = session.exec(stmt).first()
    if not user:
        raise not_found(
            "User not found",
            field="email",
            reason="user_not_found",
        )
    if user.status != UserStatus.active:
        raise forbid(
            "User is inactive",
            field="email",
            reason="user_inactive",
        )
    return user


def _count_active_admins(*, session: Session, company_id: UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(CompanyMember)
        .where(CompanyMember.company_id == company_id)
        .where(CompanyMember.status == MemberStatus.active)
        .where(CompanyMember.role == MemberRole.company_admin)
    )
    return int(session.exec(stmt).one())


def create_company(*, session: Session, user_id: UUID, name: str) -> tuple[Company, CompanyMember]:
    normalized_name = (name or "").strip()
    if not normalized_name:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Invalid company name",
            details=[{"field": "name", "reason": "empty_after_trim"}],
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
    stmt = (
        select(Company, CompanyMember.role)
        .join(CompanyMember, CompanyMember.company_id == Company.id)
        .where(CompanyMember.user_id == user_id)
        .where(CompanyMember.status == MemberStatus.active)
        .order_by(Company.created_at.desc())
    )
    return list(session.exec(stmt).all())


def get_company_for_member(
    *, session: Session, company_id: UUID, user_id: UUID
) -> tuple[Company, MemberRole]:
    company = _load_company_or_404(session=session, company_id=company_id)
    member = load_company_member_active_or_403(
        session=session, company_id=company_id, user_id=user_id
    )
    return company, member.role


def add_member_by_email(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    email: str,
) -> tuple[CompanyMember, User]:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)
    user = _load_user_by_email_or_404(session=session, email=email)

    stmt = (
        select(CompanyMember)
        .where(CompanyMember.company_id == company_id)
        .where(CompanyMember.user_id == user.id)
    )
    existing = session.exec(stmt).first()
    if existing and existing.status == MemberStatus.active:
        raise AppError.conflict(
            ErrorCode.CONFLICT,
            "User is already a member of this company",
            field="email",
        )

    if existing and existing.status == MemberStatus.removed:
        existing.status = MemberStatus.active
        existing.role = MemberRole.member
        existing.removed_at = None
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing, user

    member = CompanyMember(
        company_id=company_id,
        user_id=user.id,
        role=MemberRole.member,
        status=MemberStatus.active,
    )
    session.add(member)
    session.commit()
    session.refresh(member)
    return member, user


def list_company_members(
    *, session: Session, company_id: UUID, actor_user_id: UUID
) -> list[tuple[CompanyMember, User]]:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    stmt = (
        select(CompanyMember, User)
        .join(User, User.id == CompanyMember.user_id)
        .where(CompanyMember.company_id == company_id)
        .order_by(CompanyMember.joined_at.asc())
    )
    return list(session.exec(stmt).all())


def update_member(
    *,
    session: Session,
    company_id: UUID,
    member_id: UUID,
    actor_user_id: UUID,
    role: MemberRole | None,
    status: MemberStatus | None,
) -> tuple[CompanyMember, User]:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    stmt = (
        select(CompanyMember)
        .where(CompanyMember.id == member_id)
        .where(CompanyMember.company_id == company_id)
    )
    member = session.exec(stmt).first()
    if not member:
        raise not_found("Company member not found", field="member_id")

    if role is None and status is None:
        user = session.get(User, member.user_id)
        if not user:
            raise not_found("User not found", field="user_id")
        return member, user

    admin_demotion = (
        member.status == MemberStatus.active
        and member.role == MemberRole.company_admin
        and (
            role == MemberRole.member
            or status == MemberStatus.removed
        )
    )
    if admin_demotion and _count_active_admins(session=session, company_id=company_id) <= 1:
        raise forbid(
            "Cannot remove or demote the last company admin",
            field="member_id",
            reason="last_company_admin",
        )

    if role is not None:
        member.role = role

    if status is not None:
        member.status = status
        if status == MemberStatus.removed:
            member.removed_at = datetime.utcnow()
        else:
            member.removed_at = None

    session.add(member)
    session.commit()
    session.refresh(member)

    user = session.get(User, member.user_id)
    if not user:
        raise not_found("User not found", field="user_id")
    return member, user


def get_system_prompt(*, session: Session, company_id: UUID, user_id: UUID) -> Company:
    company = _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=user_id)
    return company


def update_system_prompt(
    *,
    session: Session,
    company_id: UUID,
    user_id: UUID,
    system_prompt: str | None,
) -> Company:
    company = _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=user_id)

    normalized = (system_prompt or "").strip()
    company.system_prompt = normalized or None
    session.add(company)
    session.commit()
    session.refresh(company)
    return company
