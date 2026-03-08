from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.schemas import ApiResponse
from app.rule import service as rule_service
from app.rule.schemas import PersonalRuleOut, PersonalRuleToggleEnabledIn


router = APIRouter(prefix="/v1", tags=["personal-rules"])


@router.get(
    "/rules/personal",
    response_model=ApiResponse[list[PersonalRuleOut]],
)
def list_personal_rules(
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rows = rule_service.list_personal_rules(
        session=session,
        actor_user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=rows)


@router.patch(
    "/rules/personal/{stable_key}/enabled",
    response_model=ApiResponse[PersonalRuleOut],
)
def toggle_personal_rule_enabled(
    stable_key: str,
    payload: PersonalRuleToggleEnabledIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = rule_service.toggle_personal_rule_enabled(
        session=session,
        actor_user_id=principal.user_id,
        stable_key=stable_key,
        enabled=payload.enabled,
    )
    return ApiResponse(ok=True, data=row)
