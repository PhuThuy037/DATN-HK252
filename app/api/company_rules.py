from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.schemas import ApiResponse
from app.rule import service as rule_service
from app.rule.schemas import (
    CompanyRuleCreateIn,
    CompanyRuleOut,
    CompanyRuleToggleEnabledIn,
    CompanyRuleUpdateIn,
    RuleChangeLogOut,
)

router = APIRouter(prefix="/v1", tags=["rule-set-rules"])


@router.get(
    "/rule-sets/{rule_set_id}/rules",
    response_model=ApiResponse[list[CompanyRuleOut]],
)
def list_rule_set_rules(
    rule_set_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rows = rule_service.list_company_rules(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=rows)


@router.get(
    "/rule-sets/{rule_set_id}/rules/change-logs",
    response_model=ApiResponse[list[RuleChangeLogOut]],
)
def list_rule_set_rule_change_logs(
    rule_set_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = rule_service.list_company_rule_change_logs(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
        limit=limit,
    )
    return ApiResponse(ok=True, data=rows)


@router.post(
    "/rule-sets/{rule_set_id}/rules",
    response_model=ApiResponse[CompanyRuleOut],
)
def create_rule_set_rule(
    rule_set_id: UUID,
    payload: CompanyRuleCreateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = rule_service.create_company_custom_rule(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)


@router.patch(
    "/rule-sets/{rule_set_id}/rules/{rule_id}",
    response_model=ApiResponse[CompanyRuleOut],
)
def update_rule_set_rule(
    rule_set_id: UUID,
    rule_id: UUID,
    payload: CompanyRuleUpdateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = rule_service.update_company_rule(
        session=session,
        company_id=rule_set_id,
        rule_id=rule_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)


@router.delete(
    "/rule-sets/{rule_set_id}/rules/{rule_id}",
    response_model=ApiResponse[CompanyRuleOut],
)
def soft_delete_rule_set_rule(
    rule_set_id: UUID,
    rule_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = rule_service.soft_delete_company_rule(
        session=session,
        company_id=rule_set_id,
        rule_id=rule_id,
        actor_user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=row)


@router.patch(
    "/rule-sets/{rule_set_id}/rules/global/{stable_key}/enabled",
    response_model=ApiResponse[CompanyRuleOut],
)
def toggle_global_rule_enabled_for_rule_set(
    rule_set_id: UUID,
    stable_key: str,
    payload: CompanyRuleToggleEnabledIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = rule_service.toggle_global_rule_for_company(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
        stable_key=stable_key,
        enabled=payload.enabled,
    )
    return ApiResponse(ok=True, data=row)
