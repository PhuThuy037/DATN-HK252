from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.schemas import ApiResponse, Meta
from app.company import service as company_service
from app.decision.scan_engine_local import ScanEngineLocal
from app.rule import service as rule_service
from app.rule.schemas import (
    EffectiveRuleMeOut,
    RuleDetailOut,
    RuleSetRuleChangeLogOut,
    RuleSetRuleCreateOut,
    RuleSetRuleCreateIn,
    RuleSetRuleCreateWithContextIn,
    RuleSetRuleOut,
    RuleSetRuleToggleEnabledIn,
    RuleSetRuleUpdateIn,
)

router = APIRouter(prefix="/v1", tags=["personal-rules"])
_scan_engine = ScanEngineLocal(context_yaml_path="app/config/context_base.yaml")


class RuleDebugEvaluateIn(BaseModel):
    content: str


class RuleDebugMatchOut(BaseModel):
    rule_id: UUID
    stable_key: str
    name: str
    action: str
    priority: int


class RuleDebugEvaluateOut(BaseModel):
    final_action: str
    matched_rules: list[RuleDebugMatchOut]
    signals: dict[str, Any]


@router.get(
    "/rules/me/effective",
    response_model=ApiResponse[list[EffectiveRuleMeOut]],
)
def list_my_effective_rules(
    session: SessionDep,
    principal: CurrentPrincipal,
    limit: int = Query(default=20, ge=1, le=200),
    cursor: str | None = Query(default=None),
):
    rows, next_cursor, has_more, total = (
        rule_service.list_effective_rules_for_current_user_paginated(
            session=session,
            actor_user_id=principal.user_id,
            limit=limit,
            cursor=cursor,
        )
    )
    return ApiResponse(
        ok=True,
        data=rows,
        meta=Meta(
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
            limit=limit,
        ),
    )


@router.post(
    "/rules/debug/evaluate",
    response_model=ApiResponse[RuleDebugEvaluateOut],
)
async def debug_evaluate_rules_for_current_user(
    payload: RuleDebugEvaluateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    text = str(payload.content or "").strip()
    rows = company_service.list_my_companies(
        session=session,
        user_id=principal.user_id,
    )
    rule_set_id = rows[0][0].id if rows else None

    scan_out = await _scan_engine.scan(
        session=session,
        text=text,
        company_id=rule_set_id,
        user_id=principal.user_id,
    )

    return ApiResponse(
        ok=True,
        data=RuleDebugEvaluateOut(
            final_action=scan_out["final_action"].value,
            matched_rules=[
                RuleDebugMatchOut(
                    rule_id=m.rule_id,
                    stable_key=m.stable_key,
                    name=m.name,
                    action=m.action.value,
                    priority=int(m.priority),
                )
                for m in list(scan_out.get("matches") or [])
            ],
            signals=dict(scan_out.get("signals") or {}),
        ),
    )


@router.get(
    "/rules/{rule_id}",
    response_model=ApiResponse[RuleDetailOut],
)
def get_rule_detail(
    rule_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = rule_service.get_rule_detail(
        session=session,
        rule_id=rule_id,
        actor_user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=row)


@router.get(
    "/rule-sets/{rule_set_id}/rules",
    response_model=ApiResponse[list[RuleSetRuleOut]],
)
def list_personal_rules(
    rule_set_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
    limit: int = Query(default=20, ge=1, le=200),
    cursor: str | None = Query(default=None),
    tab: Literal["my", "global", "all"] = Query(default="all"),
):
    rows, next_cursor, has_more, total = rule_service.list_company_rules_paginated(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
        limit=limit,
        cursor=cursor,
        tab=tab,
    )
    return ApiResponse(
        ok=True,
        data=rows,
        meta=Meta(
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
            limit=limit,
        ),
    )


@router.get(
    "/rule-sets/{rule_set_id}/rules/change-logs",
    response_model=ApiResponse[list[RuleSetRuleChangeLogOut]],
)
def list_personal_rule_change_logs(
    rule_set_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
    limit: int = Query(default=20, ge=1, le=200),
    cursor: str | None = Query(default=None),
):
    rows, next_cursor, has_more, total = (
        rule_service.list_company_rule_change_logs_paginated(
            session=session,
            company_id=rule_set_id,
            actor_user_id=principal.user_id,
            limit=limit,
            cursor=cursor,
        )
    )
    return ApiResponse(
        ok=True,
        data=rows,
        meta=Meta(
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
            limit=limit,
        ),
    )


@router.post(
    "/rule-sets/{rule_set_id}/rules",
    response_model=ApiResponse[RuleSetRuleCreateOut],
)
def create_personal_rule(
    rule_set_id: UUID,
    payload: RuleSetRuleCreateIn | RuleSetRuleCreateWithContextIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rule_payload = payload.rule if isinstance(payload, RuleSetRuleCreateWithContextIn) else payload
    context_terms = (
        payload.context_terms if isinstance(payload, RuleSetRuleCreateWithContextIn) else []
    )
    row = rule_service.create_company_custom_rule(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
        payload=rule_payload,
        context_terms=context_terms,
    )
    return ApiResponse(ok=True, data=row)


@router.patch(
    "/rule-sets/{rule_set_id}/rules/{rule_id}",
    response_model=ApiResponse[RuleSetRuleOut],
)
def update_personal_rule(
    rule_set_id: UUID,
    rule_id: UUID,
    payload: RuleSetRuleUpdateIn,
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
    response_model=ApiResponse[RuleSetRuleOut],
)
def soft_delete_personal_rule(
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
    response_model=ApiResponse[RuleSetRuleOut],
)
def toggle_global_rule_enabled_for_personal_scope(
    rule_set_id: UUID,
    stable_key: str,
    payload: RuleSetRuleToggleEnabledIn,
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
