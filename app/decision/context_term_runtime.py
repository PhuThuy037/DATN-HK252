from __future__ import annotations

from dataclasses import dataclass
import time
from threading import RLock
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from app.decision.detectors.local_regex_detector import ContextHint
from app.rag.models.context_term import ContextTerm


@dataclass(slots=True)
class ContextRuntimeOverrides:
    regex_hints: dict[str, list[ContextHint]]
    persona_keywords: dict[str, list[str]]
    exact_terms: list[str]


_CACHE_TTL_SECONDS = 5.0
_cache_lock = RLock()
_cache: dict[Optional[UUID], tuple[float, ContextRuntimeOverrides]] = {}


def _clone_overrides(data: ContextRuntimeOverrides) -> ContextRuntimeOverrides:
    return ContextRuntimeOverrides(
        regex_hints={k: list(v) for k, v in data.regex_hints.items()},
        persona_keywords={k: list(v) for k, v in data.persona_keywords.items()},
        exact_terms=list(data.exact_terms),
    )


def _get_cached(company_id: Optional[UUID]) -> ContextRuntimeOverrides | None:
    with _cache_lock:
        entry = _cache.get(company_id)
        if not entry:
            return None
        expires_at, data = entry
        if expires_at <= time.monotonic():
            _cache.pop(company_id, None)
            return None
        return _clone_overrides(data)


def _set_cached(company_id: Optional[UUID], data: ContextRuntimeOverrides) -> None:
    with _cache_lock:
        _cache[company_id] = (time.monotonic() + _CACHE_TTL_SECONDS, data)


def load_context_runtime_overrides(
    *,
    session: Session,
    company_id: Optional[UUID],
) -> ContextRuntimeOverrides:
    cached = _get_cached(company_id)
    if cached is not None:
        return cached

    stmt = select(ContextTerm).where(ContextTerm.enabled.is_(True))
    if company_id is None:
        stmt = stmt.where(ContextTerm.company_id.is_(None))
    else:
        stmt = stmt.where(
            (ContextTerm.company_id.is_(None)) | (ContextTerm.company_id == company_id)
        )
    # Make "latest wins" deterministic for dedup assignment below.
    stmt = stmt.order_by(ContextTerm.created_at.asc(), ContextTerm.id.asc())

    rows = list(session.exec(stmt).all())

    regex_hints: dict[str, list[ContextHint]] = {
        "PHONE": [],
        "CCCD": [],
        "TAX_ID": [],
    }
    persona_keywords: dict[str, list[str]] = {}
    exact_terms: list[str] = []

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
            continue

        if et in {"INTERNAL_CODE", "CUSTOM_SECRET", "PROPRIETARY_IDENTIFIER"}:
            exact_terms.append(term)

    for hints in regex_hints.values():
        hints.sort(key=lambda h: h.term)
    for kws in persona_keywords.values():
        kws.sort()
    exact_terms = sorted({t for t in exact_terms if t})

    out = ContextRuntimeOverrides(
        regex_hints=regex_hints,
        persona_keywords=persona_keywords,
        exact_terms=exact_terms,
    )
    _set_cached(company_id, out)
    return _clone_overrides(out)
