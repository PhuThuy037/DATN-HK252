from __future__ import annotations
from app.db import all_models
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from app.db.engine import engine
from app.rag.models.policy_document import PolicyDocument


POLICY_MD_PATH = Path("app/rag/policies/policy_rules.md")
DOC_TITLE = "Global Policy Rules"
DOC_TYPE = "policy"


def upsert_policy_document(
    *,
    session: Session,
    company_id: Optional[UUID],
    title: str,
    doc_type: str,
    content: str,
) -> PolicyDocument:
    existing = session.exec(
        select(PolicyDocument)
        .where(PolicyDocument.company_id == company_id)
        .where(PolicyDocument.title == title)
        .where(PolicyDocument.doc_type == doc_type)
    ).first()

    if existing:
        existing.content = content
        existing.enabled = True
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    doc = PolicyDocument(
        company_id=company_id,
        title=title,
        content=content,
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
            title=DOC_TITLE,
            doc_type=DOC_TYPE,
            content=content,
        )
        print("[seed_policy_docs] upserted policy_document:", doc.id)


if __name__ == "__main__":
    main()