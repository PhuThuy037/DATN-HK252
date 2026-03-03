from __future__ import annotations
from app.db import all_models
import hashlib
from dataclasses import dataclass
from typing import Iterable, Optional
from uuid import UUID

from sqlmodel import Session, select

from app.db.engine import engine
from app.rag.models.policy_document import PolicyDocument
from app.rag.models.policy_chunk import PolicyChunk


# ----------------------------
# helpers
# ----------------------------
def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(s: str) -> str:
    # MVP: strip nhẹ, tránh hash khác nhau vì whitespace thừa
    return (s or "").strip()


@dataclass(frozen=True)
class ChunkConfig:
    chunk_size: int = 400
    overlap: int = 80
    min_chunk_len: int = 50


def chunk_text(text: str, cfg: ChunkConfig) -> list[str]:
    t = normalize_text(text)
    if not t:
        return []

    size = cfg.chunk_size
    overlap = cfg.overlap
    assert size > 0 and 0 <= overlap < size

    out: list[str] = []
    start = 0
    n = len(t)

    while start < n:
        end = min(n, start + size)
        chunk = t[start:end].strip()
        if len(chunk) >= cfg.min_chunk_len:
            out.append(chunk)

        if end >= n:
            break

        # trượt cửa sổ với overlap
        start = max(0, end - overlap)

        # chống loop vô hạn (cực hiếm)
        if start >= end:
            start = end

    return out


# ----------------------------
# upsert logic
# ----------------------------
def upsert_chunks_for_document(
    *,
    session: Session,
    doc: PolicyDocument,
    cfg: ChunkConfig,
) -> int:
    """
    Upsert policy_chunks cho 1 document:
    - Unique(order): (document_id, chunk_index)
    - De-dup theo content_hash (nếu muốn tránh lưu trùng giữa docs thì dùng unique global,
      nhưng DB mày đang index content_hash thôi, không unique => ta upsert theo order là chính).
    """
    chunks = chunk_text(doc.content, cfg)
    if not chunks:
        return 0

    upserted = 0

    # load existing by doc_id (để update nếu thay content)
    existing_rows = session.exec(
        select(PolicyChunk).where(PolicyChunk.document_id == doc.id)
    ).all()
    existing_by_index = {c.chunk_index: c for c in existing_rows}

    for idx, content in enumerate(chunks):
        h = sha256_hex(content)

        row = existing_by_index.get(idx)
        if row:
            # update nếu content thay đổi
            if row.content_hash != h or row.content != content:
                row.content = content
                row.content_hash = h
                # giữ company_id, document_id
                upserted += 1
        else:
            session.add(
                PolicyChunk(
                    document_id=doc.id,
                    company_id=doc.company_id,
                    chunk_index=idx,
                    content=content,
                    content_hash=h,
                )
            )
            upserted += 1

    # nếu doc content bị shorten => chunks cũ dư index lớn hơn
    max_idx = len(chunks) - 1
    stale = [c for c in existing_rows if c.chunk_index > max_idx]
    for c in stale:
        session.delete(c)
        upserted += 1

    return upserted


def iter_documents(
    *,
    session: Session,
    company_id: Optional[UUID] = None,
    doc_type: Optional[str] = None,
) -> Iterable[PolicyDocument]:
    stmt = select(PolicyDocument).where(PolicyDocument.enabled == True)  # noqa: E712
    if company_id is None:
        stmt = stmt.where(PolicyDocument.company_id.is_(None))
    else:
        stmt = stmt.where(PolicyDocument.company_id == company_id)
    if doc_type:
        stmt = stmt.where(PolicyDocument.doc_type == doc_type)
    return session.exec(stmt).all()


# ----------------------------
# main
# ----------------------------
def main():
    cfg = ChunkConfig(chunk_size=400, overlap=80, min_chunk_len=50)

    with Session(engine) as session:
        docs = list(iter_documents(session=session, company_id=None, doc_type=None))
        if not docs:
            print("[seed_policy_chunks] no enabled policy_documents found")
            return

        total = 0
        for doc in docs:
            n = upsert_chunks_for_document(session=session, doc=doc, cfg=cfg)
            total += n
            print(f"[seed_policy_chunks] doc={doc.id} title={doc.title!r} upserted={n}")

        session.commit()
        print(f"[seed_policy_chunks] DONE total_upserted={total}")


if __name__ == "__main__":
    main()