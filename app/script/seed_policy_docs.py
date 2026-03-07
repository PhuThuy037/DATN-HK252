from __future__ import annotations
from app.db import all_models  # noqa: F401
import hashlib
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from app.db.engine import engine
from app.rag.models.policy_document import PolicyDocument


POLICY_MD_PATH = Path("app/rag/policies/policy_rules.md")
DOC_TITLE = "Global Policy Rules"
DOC_TYPE = "policy"
DOC_STABLE_KEY = "global.policy.rules.default"


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def upsert_policy_document(
    *,
    session: Session,
    company_id: Optional[UUID],
    stable_key: str,
    title: str,
    doc_type: str,
    content: str,
) -> PolicyDocument:
    content_hash = _sha256_hex(content)
    existing = session.exec(
        select(PolicyDocument)
        .where(PolicyDocument.company_id == company_id)
        .where(PolicyDocument.stable_key == stable_key)
        .where(PolicyDocument.deleted_at.is_(None))
    ).first()

    if existing:
        existing.content = content
        existing.content_hash = content_hash
        existing.title = title
        existing.doc_type = doc_type
        existing.enabled = True
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    doc = PolicyDocument(
        company_id=company_id,
        stable_key=stable_key,
        title=title,
        content=content,
        content_hash=content_hash,
        version=1,
        doc_type=doc_type,
        enabled=True,
        created_by=None,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def main():
    content = POLICY_MD_PATH.read_text(encoding="utf-8")

    with Session(engine) as session:
        doc = upsert_policy_document(
            session=session,
            company_id=None,  # global
            stable_key=DOC_STABLE_KEY,
            title=DOC_TITLE,
            doc_type=DOC_TYPE,
            content=content,
        )
        print("[seed_policy_docs] upserted policy_document:", doc.id)


if __name__ == "__main__":
    main()
