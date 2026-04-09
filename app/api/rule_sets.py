from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal, require_admin
from app.common.schemas import ApiResponse
from app.company import service as company_service
from app.company.schemas import RuleSetCreateIn, RuleSetOut
from app.rule import service as rule_service
from app.rule.schemas import RuleSetRuleOut

router = APIRouter(
    prefix="/v1",
    tags=["rule-sets"],
    dependencies=[Depends(require_admin)],
)


def _rule_set_out(*, rule_set, my_role) -> RuleSetOut:
    return RuleSetOut(
        id=rule_set.id,
        name=rule_set.name,
        status=rule_set.status,
        created_at=rule_set.created_at,
        my_role=my_role,
    )


@router.post("/rule-sets", response_model=ApiResponse[RuleSetOut])
def create_rule_set(
    payload: RuleSetCreateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rule_set, owner_member = company_service.create_company(
        session=session,
        user_id=principal.user_id,
        name=payload.name,
    )
    return ApiResponse(
        ok=True,
        data=_rule_set_out(rule_set=rule_set, my_role=owner_member.role),
    )


@router.get("/rule-sets/me", response_model=ApiResponse[list[RuleSetOut]])
def list_my_rule_sets(
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rows = company_service.list_my_companies(
        session=session,
        user_id=principal.user_id,
    )
    data = [_rule_set_out(rule_set=c, my_role=role) for c, role in rows]
    return ApiResponse(ok=True, data=data)


@router.get("/rule-sets/me/rules", response_model=ApiResponse[list[RuleSetRuleOut]])
def list_my_rule_set_rules(
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rows = company_service.list_my_companies(
        session=session,
        user_id=principal.user_id,
    )
    if not rows:
        return ApiResponse(ok=True, data=[])

    rule_set, _ = rows[0]
    rules = rule_service.list_company_rules(
        session=session,
        company_id=rule_set.id,
        actor_user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=rules)


@router.get("/rule-sets/{rule_set_id}", response_model=ApiResponse[RuleSetOut])
def get_rule_set(
    rule_set_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rule_set, role = company_service.get_company_for_member(
        session=session,
        company_id=rule_set_id,
        user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=_rule_set_out(rule_set=rule_set, my_role=role))
