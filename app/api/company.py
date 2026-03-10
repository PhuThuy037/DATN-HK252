from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.schemas import ApiResponse
from app.company import service as company_service
from app.company.schemas import CompanyCreateIn, CompanyOut

router = APIRouter(prefix="/v1", tags=["rule-sets"])


def _company_out(*, company, my_role) -> CompanyOut:
    return CompanyOut(
        id=company.id,
        name=company.name,
        status=company.status,
        created_at=company.created_at,
        my_role=my_role,
    )


@router.post("/rule-sets", response_model=ApiResponse[CompanyOut])
def create_rule_set(
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


@router.get("/rule-sets/me", response_model=ApiResponse[list[CompanyOut]])
def list_my_rule_sets(
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rows = company_service.list_my_companies(
        session=session,
        user_id=principal.user_id,
    )
    data = [_company_out(company=c, my_role=role) for c, role in rows]
    return ApiResponse(ok=True, data=data)


@router.get("/rule-sets/{rule_set_id}", response_model=ApiResponse[CompanyOut])
def get_rule_set(
    rule_set_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    company, role = company_service.get_company_for_member(
        session=session,
        company_id=rule_set_id,
        user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=_company_out(company=company, my_role=role))
