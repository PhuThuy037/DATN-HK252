from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.schemas import ApiResponse
from app.company import service as company_service
from app.company.schemas import CompanySystemPromptOut, CompanySystemPromptUpdateIn

router = APIRouter(prefix="/v1", tags=["rule-set-settings"])


@router.get(
    "/rule-sets/{rule_set_id}/settings/system-prompt",
    response_model=ApiResponse[CompanySystemPromptOut],
)
def get_rule_set_system_prompt(
    rule_set_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    company = company_service.get_system_prompt(
        session=session,
        company_id=rule_set_id,
        user_id=principal.user_id,
    )
    return ApiResponse(
        ok=True,
        data=CompanySystemPromptOut(
            rule_set_id=company.id,
            system_prompt=company.system_prompt,
        ),
    )


@router.put(
    "/rule-sets/{rule_set_id}/settings/system-prompt",
    response_model=ApiResponse[CompanySystemPromptOut],
)
def update_rule_set_system_prompt(
    rule_set_id: UUID,
    payload: CompanySystemPromptUpdateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    company = company_service.update_system_prompt(
        session=session,
        company_id=rule_set_id,
        user_id=principal.user_id,
        system_prompt=payload.system_prompt,
    )
    return ApiResponse(
        ok=True,
        data=CompanySystemPromptOut(
            rule_set_id=company.id,
            system_prompt=company.system_prompt,
        ),
    )

