from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlmodel import Session, delete, select

from app.common.enums import MemberRole
from app.common.error_codes import ErrorCode
from app.common.errors import AppError
from app.company.model import Company
from app.permissions.core import forbid, not_found
from app.permissions.loaders.conversation import load_company_member_active_or_403
from app.rag.models.policy_chunk import PolicyChunk
from app.rag.models.policy_chunk_embedding import PolicyChunkEmbedding
from app.rag.models.policy_document import PolicyDocument
from app.rag.models.policy_ingest_job import PolicyIngestJob
from app.rag.models.policy_ingest_job_item import PolicyIngestJobItem
from app.policy.queue import enqueue_policy_ingest_job
from app.policy.schemas import (
    PolicyDocumentOut,
    PolicyIngestJobCreateIn,
    PolicyIngestJobDetailOut,
    PolicyIngestJobItemOut,
    PolicyIngestJobOut,
    PolicyIngestStatus,
)
from app.core.config import get_settings


EMBED_MODEL = "mxbai-embed-large"
EMBED_DIM = 1024


@dataclass(frozen=True)
class PreparedIngestItem:
    stable_key: str
    title: str
    content: str
    doc_type: str
    enabled: bool
    content_hash: str
    attempt: int


@dataclass(frozen=True)
class ChunkConfig:
    chunk_size: int = 400
    overlap: int = 80
    min_chunk_len: int = 50


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_non_empty(*, value: str | None, field: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid {field}",
            details=[{"field": field, "reason": "empty_after_trim"}],
        )
    return normalized


def _normalize_stable_key(stable_key: str) -> str:
    return _normalize_non_empty(value=stable_key, field="stable_key").lower()


def _load_company_or_404(*, session: Session, company_id: UUID) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise not_found("Company not found", field="company_id")
    return company


def _require_company_admin(*, session: Session, company_id: UUID, user_id: UUID) -> None:
    member = load_company_member_active_or_403(
        session=session,
        company_id=company_id,
        user_id=user_id,
    )
    if member.role != MemberRole.company_admin:
        raise forbid(
            "Company admin required",
            field="company_id",
            reason="not_company_admin",
        )


def _to_policy_doc_out(*, row: PolicyDocument) -> PolicyDocumentOut:
    return PolicyDocumentOut(
        id=row.id,
        rule_set_id=row.company_id,
        stable_key=row.stable_key,
        title=row.title,
        doc_type=row.doc_type,
        content_hash=row.content_hash,
        version=row.version,
        enabled=row.enabled,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _to_job_out(*, row: PolicyIngestJob) -> PolicyIngestJobOut:
    return PolicyIngestJobOut(
        id=row.id,
        rule_set_id=row.company_id,
        requested_by=row.requested_by,
        retry_of_job_id=row.retry_of_job_id,
        status=PolicyIngestStatus(row.status),
        total_items=row.total_items,
        success_items=row.success_items,
        failed_items=row.failed_items,
        skipped_items=row.skipped_items,
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_job_item_out(*, row: PolicyIngestJobItem) -> PolicyIngestJobItemOut:
    return PolicyIngestJobItemOut(
        id=row.id,
        stable_key=row.stable_key,
        title=row.title,
        doc_type=row.doc_type,
        content_hash=row.content_hash,
        enabled=row.enabled,
        status=PolicyIngestStatus(row.status),
        document_id=row.document_id,
        error_message=row.error_message,
        attempt=row.attempt,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _prepare_items_from_payload(*, payload: PolicyIngestJobCreateIn) -> list[PreparedIngestItem]:
    seen: set[str] = set()
    out: list[PreparedIngestItem] = []

    for item in payload.items:
        stable_key = _normalize_stable_key(item.stable_key)
        if stable_key in seen:
            raise AppError(
                422,
                ErrorCode.VALIDATION_ERROR,
                "Duplicate stable_key in request",
                details=[{"field": "stable_key", "reason": "duplicate_in_request"}],
            )
        seen.add(stable_key)

        title = _normalize_non_empty(value=item.title, field="title")
        content = _normalize_non_empty(value=item.content, field="content")
        doc_type = _normalize_non_empty(value=item.doc_type, field="doc_type").lower()

        out.append(
            PreparedIngestItem(
                stable_key=stable_key,
                title=title,
                content=content,
                doc_type=doc_type,
                enabled=bool(item.enabled),
                content_hash=_sha256_hex(content),
                attempt=1,
            )
        )

    return out


def _create_job_rows(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    items: list[PreparedIngestItem],
    retry_of_job_id: UUID | None = None,
) -> PolicyIngestJob:
    job = PolicyIngestJob(
        company_id=company_id,
        requested_by=actor_user_id,
        retry_of_job_id=retry_of_job_id,
        status=PolicyIngestStatus.pending.value,
        total_items=len(items),
        success_items=0,
        failed_items=0,
        skipped_items=0,
        payload_json={
            "items": [
                {
                    "stable_key": i.stable_key,
                    "title": i.title,
                    "doc_type": i.doc_type,
                    "enabled": i.enabled,
                    "content_hash": i.content_hash,
                    "attempt": i.attempt,
                }
                for i in items
            ]
        },
    )
    session.add(job)
    session.flush()

    for i in items:
        session.add(
            PolicyIngestJobItem(
                job_id=job.id,
                company_id=company_id,
                stable_key=i.stable_key,
                title=i.title,
                doc_type=i.doc_type,
                content=i.content,
                content_hash=i.content_hash,
                enabled=i.enabled,
                status=PolicyIngestStatus.pending.value,
                attempt=max(1, int(i.attempt)),
            )
        )

    session.commit()
    session.refresh(job)
    return job


def list_company_policy_documents(
    *, session: Session, company_id: UUID, actor_user_id: UUID
) -> list[PolicyDocumentOut]:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    # Tenant filtering for policy browsing:
    # global policies + current personal policies (legacy key: company_id).
    rows = list(
        session.exec(
            select(PolicyDocument)
            .where(
                (PolicyDocument.company_id.is_(None))
                | (PolicyDocument.company_id == company_id)
            )
            .where(PolicyDocument.deleted_at.is_(None))
            .order_by(PolicyDocument.created_at.desc())
        ).all()
    )
    return [_to_policy_doc_out(row=r) for r in rows]


def toggle_company_policy_document_enabled(
    *,
    session: Session,
    company_id: UUID,
    document_id: UUID,
    actor_user_id: UUID,
    enabled: bool,
) -> PolicyDocumentOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    row = session.get(PolicyDocument, document_id)
    if not row or row.company_id != company_id or row.deleted_at is not None:
        raise not_found("Policy document not found", field="document_id")

    row.enabled = bool(enabled)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_policy_doc_out(row=row)


def soft_delete_company_policy_document(
    *,
    session: Session,
    company_id: UUID,
    document_id: UUID,
    actor_user_id: UUID,
) -> PolicyDocumentOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    row = session.get(PolicyDocument, document_id)
    if not row or row.company_id != company_id or row.deleted_at is not None:
        raise not_found("Policy document not found", field="document_id")

    row.enabled = False
    row.deleted_at = _utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_policy_doc_out(row=row)


def create_policy_ingest_job(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    payload: PolicyIngestJobCreateIn,
) -> PolicyIngestJobOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    items = _prepare_items_from_payload(payload=payload)
    job = _create_job_rows(
        session=session,
        company_id=company_id,
        actor_user_id=actor_user_id,
        items=items,
    )

    try:
        enqueue_policy_ingest_job(job_id=job.id)
    except Exception as e:
        job = session.get(PolicyIngestJob, job.id)
        if job:
            job.status = PolicyIngestStatus.failed.value
            job.error_json = {"message": f"enqueue_failed: {e}"}
            job.finished_at = _utcnow()
            session.add(job)
            session.commit()
        raise

    return _to_job_out(row=job)


def list_policy_ingest_jobs(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    limit: int = 50,
) -> list[PolicyIngestJobOut]:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    safe_limit = max(1, min(int(limit), 200))
    rows = list(
        session.exec(
            select(PolicyIngestJob)
            .where(PolicyIngestJob.company_id == company_id)
            .order_by(PolicyIngestJob.created_at.desc())
            .limit(safe_limit)
        ).all()
    )
    return [_to_job_out(row=r) for r in rows]


def get_policy_ingest_job_detail(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    job_id: UUID,
) -> PolicyIngestJobDetailOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    job = session.get(PolicyIngestJob, job_id)
    if not job or job.company_id != company_id:
        raise not_found("Policy ingest job not found", field="job_id")

    items = list(
        session.exec(
            select(PolicyIngestJobItem)
            .where(PolicyIngestJobItem.job_id == job_id)
            .order_by(PolicyIngestJobItem.created_at.asc())
        ).all()
    )
    base = _to_job_out(row=job)
    return PolicyIngestJobDetailOut(
        **base.model_dump(),
        error_json=job.error_json,
        items=[_to_job_item_out(row=r) for r in items],
    )


def retry_policy_ingest_job(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    source_job_id: UUID,
) -> PolicyIngestJobOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    source_job = session.get(PolicyIngestJob, source_job_id)
    if not source_job or source_job.company_id != company_id:
        raise not_found("Policy ingest job not found", field="job_id")

    failed_items = list(
        session.exec(
            select(PolicyIngestJobItem)
            .where(PolicyIngestJobItem.job_id == source_job_id)
            .where(PolicyIngestJobItem.status == PolicyIngestStatus.failed.value)
            .order_by(PolicyIngestJobItem.created_at.asc())
        ).all()
    )
    if not failed_items:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "No failed items to retry",
            details=[{"field": "job_id", "reason": "no_failed_items"}],
        )

    retry_items = [
        PreparedIngestItem(
            stable_key=i.stable_key,
            title=i.title,
            content=i.content,
            doc_type=i.doc_type,
            enabled=i.enabled,
            content_hash=i.content_hash,
            attempt=int(i.attempt) + 1,
        )
        for i in failed_items
    ]
    job = _create_job_rows(
        session=session,
        company_id=company_id,
        actor_user_id=actor_user_id,
        items=retry_items,
        retry_of_job_id=source_job_id,
    )
    try:
        enqueue_policy_ingest_job(job_id=job.id)
    except Exception as e:
        job = session.get(PolicyIngestJob, job.id)
        if job:
            job.status = PolicyIngestStatus.failed.value
            job.error_json = {"message": f"enqueue_failed: {e}"}
            job.finished_at = _utcnow()
            session.add(job)
            session.commit()
        raise
    return _to_job_out(row=job)


def _normalize_text(text: str) -> str:
    return (text or "").strip()


def _chunk_text(text: str, cfg: ChunkConfig) -> list[str]:
    t = _normalize_text(text)
    if not t:
        return []

    assert cfg.chunk_size > 0 and 0 <= cfg.overlap < cfg.chunk_size
    out: list[str] = []
    start = 0
    n = len(t)

    while start < n:
        end = min(n, start + cfg.chunk_size)
        chunk = t[start:end].strip()
        if len(chunk) >= cfg.min_chunk_len:
            out.append(chunk)

        if end >= n:
            break

        start = max(0, end - cfg.overlap)
        if start >= end:
            start = end

    return out


def _embed_texts(*, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    out: list[list[float]] = []
    with httpx.Client(base_url=base_url, timeout=30) as client:
        for text in texts:
            r = client.post(
                "/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
            emb = data.get("embedding")
            if not emb:
                raise RuntimeError(f"Empty embedding response: {data}")
            if len(emb) != EMBED_DIM:
                raise RuntimeError(
                    f"Embedding dim mismatch: got={len(emb)} expected={EMBED_DIM}"
                )
            out.append(emb)
    return out


def _replace_document_chunks_and_embeddings(
    *, session: Session, doc: PolicyDocument, cfg: ChunkConfig
) -> None:
    old_chunk_ids = session.exec(
        select(PolicyChunk.id).where(PolicyChunk.document_id == doc.id)
    ).all()
    if old_chunk_ids:
        session.exec(
            delete(PolicyChunkEmbedding).where(
                PolicyChunkEmbedding.chunk_id.in_(list(old_chunk_ids))
            )
        )
        session.exec(delete(PolicyChunk).where(PolicyChunk.document_id == doc.id))
        session.flush()

    chunks = _chunk_text(doc.content, cfg)
    if not chunks:
        return

    chunk_rows: list[PolicyChunk] = []
    for idx, content in enumerate(chunks):
        row = PolicyChunk(
            document_id=doc.id,
            company_id=doc.company_id,
            chunk_index=idx,
            content=content,
            content_hash=_sha256_hex(content),
        )
        session.add(row)
        chunk_rows.append(row)
    session.flush()

    embeddings = _embed_texts(texts=[c.content for c in chunk_rows])
    for chunk, embedding in zip(chunk_rows, embeddings):
        session.add(
            PolicyChunkEmbedding(
                chunk_id=chunk.id,
                model_name=EMBED_MODEL,
                embedding=embedding,
            )
        )
    session.flush()


def _upsert_policy_document_from_item(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    item: PolicyIngestJobItem,
    cfg: ChunkConfig,
) -> tuple[PolicyDocument, str]:
    existing = session.exec(
        select(PolicyDocument)
        .where(PolicyDocument.company_id == company_id)
        .where(PolicyDocument.stable_key == item.stable_key)
        .where(PolicyDocument.deleted_at.is_(None))
    ).first()

    if existing is None:
        doc = PolicyDocument(
            company_id=company_id,
            stable_key=item.stable_key,
            title=item.title,
            content=item.content,
            content_hash=item.content_hash,
            version=1,
            doc_type=item.doc_type,
            enabled=item.enabled,
            created_by=actor_user_id,
        )
        session.add(doc)
        session.flush()
        _replace_document_chunks_and_embeddings(session=session, doc=doc, cfg=cfg)
        return doc, "success"

    content_changed = existing.content_hash != item.content_hash
    metadata_changed = (
        existing.title != item.title
        or existing.doc_type != item.doc_type
        or bool(existing.enabled) != bool(item.enabled)
    )

    if not content_changed and not metadata_changed:
        return existing, "skipped"

    existing.title = item.title
    existing.doc_type = item.doc_type
    existing.enabled = item.enabled

    if content_changed:
        existing.content = item.content
        existing.content_hash = item.content_hash
        existing.version = int(existing.version or 1) + 1
        session.add(existing)
        session.flush()
        _replace_document_chunks_and_embeddings(session=session, doc=existing, cfg=cfg)
        return existing, "success"

    session.add(existing)
    session.flush()
    return existing, "success"


def _finalize_job(*, session: Session, job: PolicyIngestJob) -> None:
    items = list(
        session.exec(
            select(PolicyIngestJobItem).where(PolicyIngestJobItem.job_id == job.id)
        ).all()
    )
    success_items = sum(1 for i in items if i.status == PolicyIngestStatus.success.value)
    failed_items = sum(1 for i in items if i.status == PolicyIngestStatus.failed.value)
    skipped_items = sum(1 for i in items if i.status == PolicyIngestStatus.skipped.value)

    job.success_items = success_items
    job.failed_items = failed_items
    job.skipped_items = skipped_items
    job.finished_at = _utcnow()
    if failed_items > 0:
        job.status = PolicyIngestStatus.failed.value
        job.error_json = {
            "failed_items": [
                {"stable_key": i.stable_key, "error": i.error_message}
                for i in items
                if i.status == PolicyIngestStatus.failed.value
            ]
        }
    else:
        job.status = PolicyIngestStatus.success.value
        job.error_json = None
    session.add(job)
    session.commit()


def process_policy_ingest_job(*, session: Session, job_id: UUID) -> None:
    job = session.get(PolicyIngestJob, job_id)
    if not job:
        return

    if job.status != PolicyIngestStatus.pending.value:
        return

    job.status = PolicyIngestStatus.running.value
    job.started_at = _utcnow()
    job.finished_at = None
    job.error_json = None
    session.add(job)
    session.commit()

    item_ids = session.exec(
        select(PolicyIngestJobItem.id)
        .where(PolicyIngestJobItem.job_id == job_id)
        .order_by(PolicyIngestJobItem.created_at.asc())
    ).all()
    cfg = ChunkConfig()

    for item_id in item_ids:
        item = session.get(PolicyIngestJobItem, item_id)
        if not item:
            continue

        item.status = PolicyIngestStatus.running.value
        item.error_message = None
        session.add(item)
        session.commit()

        try:
            doc, outcome = _upsert_policy_document_from_item(
                session=session,
                company_id=job.company_id,
                actor_user_id=job.requested_by,
                item=item,
                cfg=cfg,
            )
            item = session.get(PolicyIngestJobItem, item_id)
            if not item:
                continue
            item.document_id = doc.id
            item.status = (
                PolicyIngestStatus.skipped.value
                if outcome == "skipped"
                else PolicyIngestStatus.success.value
            )
            item.error_message = None
            session.add(item)
            session.commit()
        except Exception as e:
            session.rollback()
            item = session.get(PolicyIngestJobItem, item_id)
            if not item:
                continue
            item.status = PolicyIngestStatus.failed.value
            item.error_message = str(e)[:1000]
            session.add(item)
            session.commit()

    job = session.get(PolicyIngestJob, job_id)
    if not job:
        return
    _finalize_job(session=session, job=job)

