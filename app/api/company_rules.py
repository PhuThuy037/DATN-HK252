from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.schemas import ApiResponse
from app.rule import service as rule_service
from app.rule.schemas import (
    CompanyRuleCreateIn,
    CompanyRuleOut,
    CompanyRuleToggleEnabledIn,
    CompanyRuleUpdateIn,
)

router = APIRouter(prefix="/v1", tags=["company-rules"])


@router.get(
    "/companies/{company_id}/rules",
    response_model=ApiResponse[list[CompanyRuleOut]],
)
def list_company_rules(
    company_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rows = rule_service.list_company_rules(
        session=session,
        company_id=company_id,
        actor_user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=rows)


@router.post(
    "/companies/{company_id}/rules",
    response_model=ApiResponse[CompanyRuleOut],
)
def create_company_rule(
    company_id: UUID,
    payload: CompanyRuleCreateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = rule_service.create_company_custom_rule(
        session=session,
        company_id=company_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)


@router.patch(
    "/companies/{company_id}/rules/{rule_id}",
    response_model=ApiResponse[CompanyRuleOut],
)
def update_company_rule(
    company_id: UUID,
    rule_id: UUID,
    payload: CompanyRuleUpdateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = rule_service.update_company_rule(
        session=session,
        company_id=company_id,
        rule_id=rule_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)


@router.delete(
    "/companies/{company_id}/rules/{rule_id}",
    response_model=ApiResponse[CompanyRuleOut],
)
def soft_delete_company_rule(
    company_id: UUID,
    rule_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = rule_service.soft_delete_company_rule(
        session=session,
        company_id=company_id,
        rule_id=rule_id,
        actor_user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=row)


@router.patch(
    "/companies/{company_id}/rules/global/{stable_key}/enabled",
    response_model=ApiResponse[CompanyRuleOut],
)
def toggle_global_rule_enabled_for_company(
    company_id: UUID,
    stable_key: str,
    payload: CompanyRuleToggleEnabledIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = rule_service.toggle_global_rule_for_company(
        session=session,
        company_id=company_id,
        actor_user_id=principal.user_id,
        stable_key=stable_key,
        enabled=payload.enabled,
    )
    return ApiResponse(ok=True, data=row)
