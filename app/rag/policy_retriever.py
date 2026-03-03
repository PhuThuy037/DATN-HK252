from __future__ import annotations

import time
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlmodel import Session, select

from app.core.config import get_settings
from app.rag.models.policy_chunk import PolicyChunk
from app.rag.models.policy_chunk_embedding import PolicyChunkEmbedding
from app.rag.models.rag_retrieval_log import RagRetrievalLog
from app.rag.embedding_cache import (
    make_key,
    get_embedding_from_cache,
    set_embedding_cache,
)


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

        # 1️⃣ Try cache
        cached = await get_embedding_from_cache(key)
        if cached is not None:
            return cached

        # 2️⃣ Call Ollama
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=10,  # giảm từ 60 xuống 10s (fail-fast)
        ) as client:
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

        # 3️⃣ Save cache (non-blocking)
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

        # NOTE:
        # - Nếu muốn multi-tenant strict: filter PolicyChunk.company_id in (company_id, None)
        # - Hiện MVP: lấy tất cả (mày có thể bật filter ở dưới)
        stmt = (
            select(PolicyChunk, PolicyChunkEmbedding)
            .join(PolicyChunkEmbedding, PolicyChunkEmbedding.chunk_id == PolicyChunk.id)
            .where(PolicyChunkEmbedding.model_name == self.embed_model)
            # .where(PolicyChunk.company_id.is_(None) if company_id is None else PolicyChunk.company_id.in_([None, company_id]))
            .order_by(PolicyChunkEmbedding.embedding.cosine_distance(q_emb))  # type: ignore
            .limit(k)
        )

        rows = session.exec(stmt).all()

        out: list[RetrievedChunk] = []
        results_json: list[dict[str, Any]] = []

        for chunk, emb_row in rows:
            dist = session.exec(
                select(PolicyChunkEmbedding.embedding.cosine_distance(q_emb)).where(  # type: ignore
                    PolicyChunkEmbedding.id == emb_row.id
                )
            ).one()

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