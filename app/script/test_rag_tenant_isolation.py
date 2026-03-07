from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from uuid import UUID

import app.db.all_models  # noqa: F401
from sqlmodel import Session, select

from app.common.enums import CompanyStatus
from app.company.model import Company
from app.db.engine import engine
from app.rag.models.policy_chunk import PolicyChunk
from app.rag.models.policy_chunk_embedding import PolicyChunkEmbedding
from app.rag.models.policy_document import PolicyDocument
from app.rag.policy_retriever import PolicyRetriever


EMBED_MODEL = "mxbai-embed-large"
EMBED_DIM = 1024


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _vec() -> list[float]:
    # Keep deterministic vector so our seeded chunks rank at top in this test.
    return [1.0] + [0.0] * (EMBED_DIM - 1)


class FakePolicyRetriever(PolicyRetriever):
    async def _embed(self, text: str) -> list[float]:
        return _vec()


@dataclass(slots=True)
class SeededCtx:
    company_a_id: UUID
    company_b_id: UUID
    marker_global_enabled: str
    marker_a_enabled: str
    marker_b_enabled: str
    marker_global_disabled: str
    marker_a_disabled: str


def _create_company(session: Session, name: str) -> Company:
    c = Company(name=name, status=CompanyStatus.active)
    session.add(c)
    session.flush()
    return c


def _create_doc(
    session: Session,
    *,
    company_id: UUID | None,
    stable_key: str,
    title: str,
    enabled: bool,
    content: str,
) -> PolicyDocument:
    d = PolicyDocument(
        company_id=company_id,
        stable_key=stable_key,
        title=title,
        content=content,
        content_hash=_sha256_hex(content),
        version=1,
        doc_type="policy",
        enabled=enabled,
        created_by=None,
    )
    session.add(d)
    session.flush()
    return d


def _create_chunk_with_embedding(
    session: Session,
    *,
    doc: PolicyDocument,
    content: str,
) -> PolicyChunk:
    chunk = PolicyChunk(
        document_id=doc.id,
        company_id=doc.company_id,
        chunk_index=0,
        content=content,
        content_hash=_sha256_hex(content),
    )
    session.add(chunk)
    session.flush()

    session.add(
        PolicyChunkEmbedding(
            chunk_id=chunk.id,
            model_name=EMBED_MODEL,
            embedding=_vec(),
        )
    )
    session.flush()
    return chunk


def _seed_test_data() -> SeededCtx:
    marker = str(int(time.time()))

    with Session(engine) as session:
        a = _create_company(session, f"Tenant A {marker}")
        b = _create_company(session, f"Tenant B {marker}")

        marker_global_enabled = f"global_enabled_{marker}"
        marker_a_enabled = f"a_enabled_{marker}"
        marker_b_enabled = f"b_enabled_{marker}"
        marker_global_disabled = f"global_disabled_{marker}"
        marker_a_disabled = f"a_disabled_{marker}"

        doc_g_on = _create_doc(
            session,
            company_id=None,
            stable_key=f"test.global.on.{marker}",
            title=f"G ON {marker}",
            enabled=True,
            content=marker_global_enabled,
        )
        doc_a_on = _create_doc(
            session,
            company_id=a.id,
            stable_key=f"test.a.on.{marker}",
            title=f"A ON {marker}",
            enabled=True,
            content=marker_a_enabled,
        )
        doc_b_on = _create_doc(
            session,
            company_id=b.id,
            stable_key=f"test.b.on.{marker}",
            title=f"B ON {marker}",
            enabled=True,
            content=marker_b_enabled,
        )
        doc_g_off = _create_doc(
            session,
            company_id=None,
            stable_key=f"test.global.off.{marker}",
            title=f"G OFF {marker}",
            enabled=False,
            content=marker_global_disabled,
        )
        doc_a_off = _create_doc(
            session,
            company_id=a.id,
            stable_key=f"test.a.off.{marker}",
            title=f"A OFF {marker}",
            enabled=False,
            content=marker_a_disabled,
        )

        _create_chunk_with_embedding(session, doc=doc_g_on, content=marker_global_enabled)
        _create_chunk_with_embedding(session, doc=doc_a_on, content=marker_a_enabled)
        _create_chunk_with_embedding(session, doc=doc_b_on, content=marker_b_enabled)
        _create_chunk_with_embedding(session, doc=doc_g_off, content=marker_global_disabled)
        _create_chunk_with_embedding(session, doc=doc_a_off, content=marker_a_disabled)

        session.commit()

        return SeededCtx(
            company_a_id=a.id,
            company_b_id=b.id,
            marker_global_enabled=marker_global_enabled,
            marker_a_enabled=marker_a_enabled,
            marker_b_enabled=marker_b_enabled,
            marker_global_disabled=marker_global_disabled,
            marker_a_disabled=marker_a_disabled,
        )


def _chunk_company_map(session: Session, chunk_ids: list[UUID]) -> dict[UUID, UUID | None]:
    if not chunk_ids:
        return {}
    rows = session.exec(select(PolicyChunk).where(PolicyChunk.id.in_(chunk_ids))).all()
    return {r.id: r.company_id for r in rows}


def _assert(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


async def main_async() -> None:
    seeded = _seed_test_data()
    retriever = FakePolicyRetriever(
        embed_model=EMBED_MODEL,
        embedding_dim=EMBED_DIM,
        top_k=100,
    )

    with Session(engine) as session:
        # Case 1: company A -> only global + A
        a_out = await retriever.retrieve(
            session=session,
            query="tenant isolation",
            company_id=seeded.company_a_id,
            message_id=None,
            top_k=100,
            log=False,
        )
        a_chunk_ids = [x.chunk_id for x in a_out]
        a_company_map = _chunk_company_map(session, a_chunk_ids)
        _assert(
            all(cid in (None, seeded.company_a_id) for cid in a_company_map.values()),
            "company A retrieval leaked non-global/non-A chunks",
        )
        a_contents = [x.content for x in a_out]
        _assert(
            seeded.marker_b_enabled not in a_contents,
            "company A retrieval leaked company B content",
        )
        _assert(
            seeded.marker_global_disabled not in a_contents
            and seeded.marker_a_disabled not in a_contents,
            "disabled policy documents were retrieved for company A",
        )
        _assert(
            seeded.marker_global_enabled in a_contents and seeded.marker_a_enabled in a_contents,
            "company A retrieval missing expected global/A enabled chunks",
        )

        # Case 2: company B -> only global + B
        b_out = await retriever.retrieve(
            session=session,
            query="tenant isolation",
            company_id=seeded.company_b_id,
            message_id=None,
            top_k=100,
            log=False,
        )
        b_chunk_ids = [x.chunk_id for x in b_out]
        b_company_map = _chunk_company_map(session, b_chunk_ids)
        _assert(
            all(cid in (None, seeded.company_b_id) for cid in b_company_map.values()),
            "company B retrieval leaked non-global/non-B chunks",
        )
        b_contents = [x.content for x in b_out]
        _assert(
            seeded.marker_a_enabled not in b_contents,
            "company B retrieval leaked company A content",
        )
        _assert(
            seeded.marker_global_enabled in b_contents and seeded.marker_b_enabled in b_contents,
            "company B retrieval missing expected global/B enabled chunks",
        )

        # Case 3: personal -> only global
        p_out = await retriever.retrieve(
            session=session,
            query="tenant isolation",
            company_id=None,
            message_id=None,
            top_k=100,
            log=False,
        )
        p_chunk_ids = [x.chunk_id for x in p_out]
        p_company_map = _chunk_company_map(session, p_chunk_ids)
        _assert(
            all(cid is None for cid in p_company_map.values()),
            "personal retrieval leaked company-specific chunks",
        )
        p_contents = [x.content for x in p_out]
        _assert(
            seeded.marker_global_enabled in p_contents,
            "personal retrieval missing expected global enabled chunk",
        )
        _assert(
            seeded.marker_a_enabled not in p_contents and seeded.marker_b_enabled not in p_contents,
            "personal retrieval leaked company A/B content",
        )

    print("ALL PASS: strict tenant isolation + enabled filter are working.")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
