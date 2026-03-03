from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.schemas import ApiResponse
from app.company.schemas import CompanySystemPromptOut, CompanySystemPromptUpdateIn
from app.company import service as company_service

router = APIRouter(prefix="/v1", tags=["company-settings"])


@router.get(
    "/companies/{company_id}/settings/system-prompt",
    response_model=ApiResponse[CompanySystemPromptOut],
)
def get_company_system_prompt(
    company_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    company = company_service.get_system_prompt(
        session=session,
        company_id=company_id,
        user_id=principal.user_id,
    )
    return ApiResponse(
        ok=True,
        data=CompanySystemPromptOut(
            company_id=company.id,
            system_prompt=company.system_prompt,
        ),
    )


@router.put(
    "/companies/{company_id}/settings/system-prompt",
    response_model=ApiResponse[CompanySystemPromptOut],
)
def update_company_system_prompt(
    company_id: UUID,
    payload: CompanySystemPromptUpdateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    company = company_service.update_system_prompt(
        session=session,
        company_id=company_id,
        user_id=principal.user_id,
        system_prompt=payload.system_prompt,
    )
    return ApiResponse(
        ok=True,
        data=CompanySystemPromptOut(
            company_id=company.id,
            system_prompt=company.system_prompt,
        ),
    )
