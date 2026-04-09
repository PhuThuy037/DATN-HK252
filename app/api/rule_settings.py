from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal, require_admin
from app.common.schemas import ApiResponse
from app.company import service as company_service
from app.company.schemas import (
    RuleSetSystemPromptOut,
    RuleSetSystemPromptUpdateIn,
)

router = APIRouter(
    prefix="/v1",
    tags=["rule-settings"],
    dependencies=[Depends(require_admin)],
)


@router.get(
    "/rule-sets/{rule_set_id}/settings/system-prompt",
    response_model=ApiResponse[RuleSetSystemPromptOut],
)
def get_rule_set_system_prompt(
    rule_set_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rule_set = company_service.get_system_prompt(
        session=session,
        company_id=rule_set_id,
        user_id=principal.user_id,
    )
    return ApiResponse(
        ok=True,
        data=RuleSetSystemPromptOut(
            rule_set_id=rule_set.id,
            system_prompt=rule_set.system_prompt,
        ),
    )


@router.put(
    "/rule-sets/{rule_set_id}/settings/system-prompt",
    response_model=ApiResponse[RuleSetSystemPromptOut],
)
def update_rule_set_system_prompt(
    rule_set_id: UUID,
    payload: RuleSetSystemPromptUpdateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rule_set = company_service.update_system_prompt(
        session=session,
        company_id=rule_set_id,
        user_id=principal.user_id,
        system_prompt=payload.system_prompt,
    )
    return ApiResponse(
        ok=True,
        data=RuleSetSystemPromptOut(
            rule_set_id=rule_set.id,
            system_prompt=rule_set.system_prompt,
        ),
    )

