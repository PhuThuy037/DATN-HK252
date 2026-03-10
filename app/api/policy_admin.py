from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.schemas import ApiResponse
from app.policy import service as policy_service
from app.policy.schemas import (
    PolicyDocumentOut,
    PolicyDocumentToggleEnabledIn,
    PolicyIngestJobCreateIn,
    PolicyIngestJobDetailOut,
    PolicyIngestJobOut,
)

router = APIRouter(prefix="/v1", tags=["rule-set-policy"])


@router.get(
    "/rule-sets/{rule_set_id}/policy-documents",
    response_model=ApiResponse[list[PolicyDocumentOut]],
)
def list_rule_set_policy_documents(
    rule_set_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    rows = policy_service.list_company_policy_documents(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=rows)


@router.patch(
    "/rule-sets/{rule_set_id}/policy-documents/{document_id}/enabled",
    response_model=ApiResponse[PolicyDocumentOut],
)
def toggle_rule_set_policy_document_enabled(
    rule_set_id: UUID,
    document_id: UUID,
    payload: PolicyDocumentToggleEnabledIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = policy_service.toggle_company_policy_document_enabled(
        session=session,
        company_id=rule_set_id,
        document_id=document_id,
        actor_user_id=principal.user_id,
        enabled=payload.enabled,
    )
    return ApiResponse(ok=True, data=row)


@router.delete(
    "/rule-sets/{rule_set_id}/policy-documents/{document_id}",
    response_model=ApiResponse[PolicyDocumentOut],
)
def soft_delete_rule_set_policy_document(
    rule_set_id: UUID,
    document_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = policy_service.soft_delete_company_policy_document(
        session=session,
        company_id=rule_set_id,
        document_id=document_id,
        actor_user_id=principal.user_id,
    )
    return ApiResponse(ok=True, data=row)


@router.post(
    "/rule-sets/{rule_set_id}/policy-ingest-jobs",
    response_model=ApiResponse[PolicyIngestJobOut],
)
def create_policy_ingest_job(
    rule_set_id: UUID,
    payload: PolicyIngestJobCreateIn,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = policy_service.create_policy_ingest_job(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
        payload=payload,
    )
    return ApiResponse(ok=True, data=row)


@router.get(
    "/rule-sets/{rule_set_id}/policy-ingest-jobs",
    response_model=ApiResponse[list[PolicyIngestJobOut]],
)
def list_policy_ingest_jobs(
    rule_set_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = policy_service.list_policy_ingest_jobs(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
        limit=limit,
    )
    return ApiResponse(ok=True, data=rows)


@router.get(
    "/rule-sets/{rule_set_id}/policy-ingest-jobs/{job_id}",
    response_model=ApiResponse[PolicyIngestJobDetailOut],
)
def get_policy_ingest_job_detail(
    rule_set_id: UUID,
    job_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = policy_service.get_policy_ingest_job_detail(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
        job_id=job_id,
    )
    return ApiResponse(ok=True, data=row)


@router.post(
    "/rule-sets/{rule_set_id}/policy-ingest-jobs/{job_id}/retry",
    response_model=ApiResponse[PolicyIngestJobOut],
)
def retry_policy_ingest_job(
    rule_set_id: UUID,
    job_id: UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    row = policy_service.retry_policy_ingest_job(
        session=session,
        company_id=rule_set_id,
        actor_user_id=principal.user_id,
        source_job_id=job_id,
    )
    return ApiResponse(ok=True, data=row)
