# app/script/seed_policy_chunk_embeddings.py
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.engine import engine
from app.rag.models.policy_chunk import PolicyChunk
from app.rag.models.policy_chunk_embedding import PolicyChunkEmbedding


EMBED_MODEL = "mxbai-embed-large"  # dims = 1024
BATCH_SIZE = 32


async def _embed_texts(
    client: httpx.AsyncClient, texts: list[str]
) -> list[list[float]]:
    """
    Ollama /api/embeddings chỉ embed 1 prompt / request (tùy version),
    nên mình gọi tuần tự trong 1 batch để dễ và ổn.
    """
    out: list[list[float]] = []
    for t in texts:
        r = await client.post(
            "/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": t},
        )
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        emb = data.get("embedding")
        if not emb:
            raise RuntimeError(f"Empty embedding response: {data}")
        out.append(emb)
    return out


def _existing_emb_chunk_ids(session: Session, chunk_ids: list) -> set:
    if not chunk_ids:
        return set()
    rows = session.exec(
        select(PolicyChunkEmbedding.chunk_id)
        .where(PolicyChunkEmbedding.chunk_id.in_(chunk_ids))
        .where(PolicyChunkEmbedding.model_name == EMBED_MODEL)
    ).all()
    return set(rows)


async def main_async():
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")

    with Session(engine) as session:
        chunks = session.exec(
            select(PolicyChunk).order_by(PolicyChunk.created_at.asc())
        ).all()

        total = len(chunks)
        if total == 0:
            print("[seed_policy_chunk_embeddings] No chunks found.")
            return

        print(
            f"[seed_policy_chunk_embeddings] total_chunks={total} model={EMBED_MODEL} base_url={base_url}"
        )

        async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
            upserted = 0

            for i in range(0, total, BATCH_SIZE):
                batch = chunks[i : i + BATCH_SIZE]
                batch_ids = [c.id for c in batch]

                exists = _existing_emb_chunk_ids(session, batch_ids)

                to_embed = [c for c in batch if c.id not in exists]
                if not to_embed:
                    continue

                texts = [c.content for c in to_embed]
                embeddings = await _embed_texts(client, texts)

                # sanity dims
                for emb in embeddings:
                    if len(emb) != 1024:
                        raise RuntimeError(
                            f"Embedding dim mismatch: got={len(emb)} expected=1024. Check model vs Vector(dims)."
                        )

                for c, emb in zip(to_embed, embeddings):
                    session.add(
                        PolicyChunkEmbedding(
                            chunk_id=c.id,
                            model_name=EMBED_MODEL,
                            embedding=emb,
                        )
                    )

                session.commit()
                upserted += len(to_embed)
                print(
                    f"[seed_policy_chunk_embeddings] batch {i // BATCH_SIZE + 1}: inserted={len(to_embed)} total_inserted={upserted}"
                )

        print(f"[seed_policy_chunk_embeddings] DONE total_inserted={upserted}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()