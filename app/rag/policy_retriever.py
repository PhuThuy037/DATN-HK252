from __future__ import annotations

import time
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlmodel import Session, select

from app.core.config import get_settings
from app.rag.embedding_cache import (
    get_embedding_from_cache,
    make_key,
    set_embedding_cache,
)
from app.rag.models.policy_chunk import PolicyChunk
from app.rag.models.policy_chunk_embedding import PolicyChunkEmbedding
from app.rag.models.policy_document import PolicyDocument
from app.rag.models.rag_retrieval_log import RagRetrievalLog


class RetrievedChunk:
    def __init__(self, *, chunk_id: UUID, content: str, dist: float, sim: float):
        self.chunk_id = chunk_id
        self.content = content
        self.dist = dist
        self.sim = sim


class PolicyRetriever:
    def __init__(
        self,
        *,
        embed_model: str,
        embedding_dim: int,
        top_k: int = 5,
    ):
        self.settings = get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")
        self.embed_model = embed_model
        self.embedding_dim = int(embedding_dim)
        self.top_k = int(top_k)

    async def _embed(self, text: str) -> list[float]:
        key = make_key(model=self.embed_model, text=text)

        cached = await get_embedding_from_cache(key)
        if cached is not None:
            return cached

        async with httpx.AsyncClient(base_url=self.base_url, timeout=10) as client:
            r = await client.post(
                "/api/embeddings",
                json={"model": self.embed_model, "prompt": text},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()

        emb = data.get("embedding")
        if not emb:
            raise RuntimeError(f"Empty embedding response: {data}")

        if len(emb) != self.embedding_dim:
            raise RuntimeError(f"dim mismatch {len(emb)} vs {self.embedding_dim}")

        await set_embedding_cache(key, emb)
        return emb

    async def retrieve(
        self,
        *,
        session: Session,
        query: str,
        company_id: Optional[UUID],
        message_id: Optional[UUID],
        top_k: Optional[int] = None,
        log: bool = True,
    ) -> list[RetrievedChunk]:
        k = int(top_k or self.top_k)
        t0 = time.perf_counter()

        q_emb = await self._embed(query)
        dist_expr = PolicyChunkEmbedding.embedding.cosine_distance(q_emb)  # type: ignore

        stmt = (
            select(PolicyChunk, PolicyChunkEmbedding, dist_expr)
            .join(PolicyDocument, PolicyDocument.id == PolicyChunk.document_id)
            .join(PolicyChunkEmbedding, PolicyChunkEmbedding.chunk_id == PolicyChunk.id)
            .where(PolicyChunkEmbedding.model_name == self.embed_model)
            .where(PolicyDocument.enabled.is_(True))
            .where(PolicyDocument.deleted_at.is_(None))
            .order_by(dist_expr)
            .limit(k)
        )

        # Tenant filtering (legacy storage key `company_id`):
        # - no rule_set scope (company_id is None): only global policies
        # - scoped conversation: global + current personal policies
        scope_id = company_id
        if scope_id is None:
            stmt = stmt.where(PolicyChunk.company_id.is_(None)).where(
                PolicyDocument.company_id.is_(None)
            )
        else:
            stmt = stmt.where(
                (PolicyChunk.company_id.is_(None)) | (PolicyChunk.company_id == scope_id)
            ).where(
                (PolicyDocument.company_id.is_(None))
                | (PolicyDocument.company_id == scope_id)
            )

        rows = session.exec(stmt).all()

        out: list[RetrievedChunk] = []
        results_json: list[dict[str, Any]] = []

        for chunk, _emb_row, dist in rows:
            dist_f = float(dist)
            sim = 1.0 - dist_f

            out.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    content=chunk.content,
                    dist=dist_f,
                    sim=sim,
                )
            )
            results_json.append(
                {
                    "chunk_id": str(chunk.id),
                    "dist": dist_f,
                    "sim": sim,
                }
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        if log:
            session.add(
                RagRetrievalLog(
                    message_id=message_id,
                    query=query,
                    top_k=k,
                    results_json={"results": results_json},
                    latency_ms=latency_ms,
                )
            )
            session.commit()

        return out
