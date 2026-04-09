from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal, require_admin
from app.common.schemas import ApiResponse
from app.suggestion import service as suggestion_service
from app.suggestion.schemas import (
    RuleSuggestionApplyIn,
    RuleSuggestionApplyOut,
    RuleSuggestionConfirmIn,
    RuleSuggestionEditIn,
    RuleSuggestionGenerateIn,
    RuleSuggestionGenerateOut,
    RuleSuggestionGetOut,
    RuleSuggestionLogOut,
    RuleSuggestionOut,
    RuleSuggestionRejectIn,
    RuleSuggestionSimulateIn,
    RuleSuggestionSimulateOut,
    SuggestionStatus,
)

router = APIRouter(
    prefix="/v1",
    tags=["rule-set-suggestions"],
    dependencies=[Depends(require_admin)],
)


@router.post(
    "/rule-sets/{rule_set_id}/rule-suggestions/generate",
    response_model=ApiResponse[RuleSuggestionGenerateOut],
)
def generate_rule_suggestion(
    rule_set_id: UUID,
    payload: RuleSuggestionGenerateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = suggestion_service.generate_rule_suggestion(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)


@router.get(
    "/rule-sets/{rule_set_id}/rule-suggestions",
    response_model=ApiResponse[list[RuleSuggestionOut]],
)
def list_rule_suggestions(
    rule_set_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
    status: SuggestionStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = suggestion_service.list_rule_suggestions(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
        status=status,
        limit=limit,
    )
    return ApiResponse(ok=True, data=rows)


@router.get(
    "/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}",
    response_model=ApiResponse[RuleSuggestionGetOut],
)
def get_rule_suggestion(
    rule_set_id: UUID,
    suggestion_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = suggestion_service.get_rule_suggestion(
        session=session,
        company_id=rule_set_id,
        suggestion_id=suggestion_id,
        actor_user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=row)


@router.get(
    "/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/logs",
    response_model=ApiResponse[list[RuleSuggestionLogOut]],
)
def list_rule_suggestion_logs(
    rule_set_id: UUID,
    suggestion_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = suggestion_service.list_rule_suggestion_logs(
        session=session,
        company_id=rule_set_id,
        suggestion_id=suggestion_id,
        actor_user_id=principal.user_id,
        limit=limit,
    )
    return ApiResponse(ok=True, data=rows)


@router.patch(
    "/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}",
    response_model=ApiResponse[RuleSuggestionOut],
)
def edit_rule_suggestion(
    rule_set_id: UUID,
    suggestion_id: UUID,
    payload: RuleSuggestionEditIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = suggestion_service.edit_rule_suggestion(
        session=session,
        company_id=rule_set_id,
        suggestion_id=suggestion_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)


@router.post(
    "/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/confirm",
    response_model=ApiResponse[RuleSuggestionOut],
)
def confirm_rule_suggestion(
    rule_set_id: UUID,
    suggestion_id: UUID,
    payload: RuleSuggestionConfirmIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = suggestion_service.confirm_rule_suggestion(
        session=session,
        company_id=rule_set_id,
        suggestion_id=suggestion_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)


@router.post(
    "/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/reject",
    response_model=ApiResponse[RuleSuggestionOut],
)
def reject_rule_suggestion(
    rule_set_id: UUID,
    suggestion_id: UUID,
    payload: RuleSuggestionRejectIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = suggestion_service.reject_rule_suggestion(
        session=session,
        company_id=rule_set_id,
        suggestion_id=suggestion_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)


@router.post(
    "/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/apply",
    response_model=ApiResponse[RuleSuggestionApplyOut],
)
def apply_rule_suggestion(
    rule_set_id: UUID,
    suggestion_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
    payload: RuleSuggestionApplyIn | None = None,
):
    row = suggestion_service.apply_rule_suggestion(
        session=session,
        company_id=rule_set_id,
        suggestion_id=suggestion_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)


@router.post(
    "/rule-sets/{rule_set_id}/rule-suggestions/{suggestion_id}/simulate",
    response_model=ApiResponse[RuleSuggestionSimulateOut],
)
def simulate_rule_suggestion(
    rule_set_id: UUID,
    suggestion_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
    payload: RuleSuggestionSimulateIn,
):
    row = suggestion_service.simulate_rule_suggestion(
        session=session,
        company_id=rule_set_id,
        suggestion_id=suggestion_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)


@router.post(
    "/rule-suggestions/{suggestion_id}/simulate",
    response_model=ApiResponse[RuleSuggestionSimulateOut],
)
def simulate_rule_suggestion_by_id(
    suggestion_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
    payload: RuleSuggestionSimulateIn,
):
    row = suggestion_service.simulate_rule_suggestion_by_id(
        session=session,
        suggestion_id=suggestion_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)
