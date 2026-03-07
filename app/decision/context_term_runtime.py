from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from app.decision.detectors.local_regex_detector import ContextHint
from app.rag.models.context_term import ContextTerm


@dataclass(slots=True)
class ContextRuntimeOverrides:
    regex_hints: dict[str, list[ContextHint]]
    persona_keywords: dict[str, list[str]]


def load_context_runtime_overrides(
    *,
    session: Session,
    company_id: Optional[UUID],
) -> ContextRuntimeOverrides:
    stmt = select(ContextTerm).where(ContextTerm.enabled.is_(True))
    if company_id is None:
        stmt = stmt.where(ContextTerm.company_id.is_(None))
    else:
        stmt = stmt.where(
            (ContextTerm.company_id.is_(None)) | (ContextTerm.company_id == company_id)
        )

    rows = list(session.exec(stmt).all())

    regex_hints: dict[str, list[ContextHint]] = {
        "PHONE": [],
        "CCCD": [],
        "TAX_ID": [],
    }
    persona_keywords: dict[str, list[str]] = {}

    # Latest rows win for same term to support company-specific override by recency.
    dedup: dict[tuple[str, str], ContextTerm] = {}
    for row in rows:
        et = str(row.entity_type or "").strip().upper()
        term = str(row.term or "").strip().lower()
        if not et or not term:
            continue
        dedup[(et, term)] = row

    for (et, term), row in dedup.items():
        if et in regex_hints:
            regex_hints[et].append(
                ContextHint(
                    term=term,
                    window_1=int(row.window_1 or 60),
                    window_2=int(row.window_2 or 20),
                    weight=float(row.weight or 1.0),
                )
            )
            continue

        if et.startswith("PERSONA_"):
            persona = et.removeprefix("PERSONA_").strip().lower()
            if not persona:
                continue
            persona_keywords.setdefault(persona, []).append(term)

    return ContextRuntimeOverrides(
        regex_hints=regex_hints,
        persona_keywords=persona_keywords,
    )
