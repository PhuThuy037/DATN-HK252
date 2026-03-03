from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.schemas import ApiResponse
from app.company import service as company_service
from app.company.schemas import (
    CompanyCreateIn,
    CompanyMemberAddIn,
    CompanyMemberOut,
    CompanyMemberUpdateIn,
    CompanyOut,
)

router = APIRouter(prefix="/v1", tags=["companies"])


def _company_out(*, company, my_role) -> CompanyOut:
    return CompanyOut(
        id=company.id,
        name=company.name,
        status=company.status,
        created_at=company.created_at,
        my_role=my_role,
    )


def _member_out(*, member, user) -> CompanyMemberOut:
    return CompanyMemberOut(
        id=member.id,
        user_id=member.user_id,
        email=user.email,
        name=user.name,
        role=member.role,
        status=member.status,
        joined_at=member.joined_at,
        removed_at=member.removed_at,
    )


@router.post("/companies", response_model=ApiResponse[CompanyOut])
def create_company(
    payload: CompanyCreateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    company, owner_member = company_service.create_company(
        session=session,
        user_id=principal.user_id,
        name=payload.name,
    )
    return ApiResponse(
        ok=True,
        data=_company_out(company=company, my_role=owner_member.role),
    )


@router.get("/companies/me", response_model=ApiResponse[list[CompanyOut]])
def list_my_companies(
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rows = company_service.list_my_companies(
        session=session,
        user_id=principal.user_id,
    )
    data = [_company_out(company=c, my_role=role) for c, role in rows]
    return ApiResponse(ok=True, data=data)


@router.get("/companies/{company_id}", response_model=ApiResponse[CompanyOut])
def get_company(
    company_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    company, role = company_service.get_company_for_member(
        session=session,
        company_id=company_id,
        user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=_company_out(company=company, my_role=role))


@router.post(
    "/companies/{company_id}/members",
    response_model=ApiResponse[CompanyMemberOut],
)
def add_company_member(
    company_id: UUID,
    payload: CompanyMemberAddIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    member, user = company_service.add_member_by_email(
        session=session,
        company_id=company_id,
        actor_user_id=principal.user_id,
        email=payload.email,
    )
    return ApiResponse(ok=True, data=_member_out(member=member, user=user))


@router.get(
    "/companies/{company_id}/members",
    response_model=ApiResponse[list[CompanyMemberOut]],
)
def list_company_members(
    company_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rows = company_service.list_company_members(
        session=session,
        company_id=company_id,
        actor_user_id=principal.user_id,
    )
    data = [_member_out(member=m, user=u) for m, u in rows]
    return ApiResponse(ok=True, data=data)


@router.patch(
    "/companies/{company_id}/members/{member_id}",
    response_model=ApiResponse[CompanyMemberOut],
)
def update_company_member(
    company_id: UUID,
    member_id: UUID,
    payload: CompanyMemberUpdateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    member, user = company_service.update_member(
        session=session,
        company_id=company_id,
        member_id=member_id,
        actor_user_id=principal.user_id,
        role=payload.role,
        status=payload.status,
    )
    return ApiResponse(ok=True, data=_member_out(member=member, user=user))
