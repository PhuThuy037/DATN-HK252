from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional
from uuid import UUID

import yaml
from sqlmodel import Session, select

import app.db.all_models  # noqa: F401
from app.db.engine import engine
from app.rag.models.context_term import ContextTerm


CONTEXT_YAML_PATH = Path("app/config/context_base.yaml")


# Base detector contexts migrated to DB-backed context_terms.
BASE_ENTITY_TERMS: dict[str, list[str]] = {
    "CCCD": ["cccd", "cÄƒn cÆ°á»›c", "cmnd"],
    "TAX_ID": ["mst", "mÃ£ sá»‘ thuáº¿", "tax code"],
    "PHONE": ["sÄ‘t", "sá»‘ Ä‘iá»‡n thoáº¡i", "hotline", "liÃªn há»‡", "sá»‘"],
}


def _normalize(term: str) -> str:
    return (term or "").strip().lower()


def _iter_persona_terms_from_yaml() -> Iterable[tuple[str, str]]:
    data = yaml.safe_load(CONTEXT_YAML_PATH.read_text(encoding="utf-8")) or {}
    personas = data.get("personas") or {}
    for persona, cfg in personas.items():
        persona_name = str(persona).strip().lower()
        if not persona_name:
            continue
        entity_type = f"PERSONA_{persona_name.upper()}"
        for kw in (cfg or {}).get("keywords") or []:
            term = _normalize(str(kw))
            if term:
                yield entity_type, term


def _upsert_term(
    *,
    session: Session,
    rule_set_id: Optional[UUID],
    entity_type: str,
    term: str,
    lang: str = "vi",
    weight: float = 1.0,
    window_1: int = 60,
    window_2: int = 20,
) -> bool:
    stmt = (
        select(ContextTerm)
        .where(ContextTerm.rule_set_id == rule_set_id)
        .where(ContextTerm.entity_type == entity_type)
        .where(ContextTerm.term == term)
        .where(ContextTerm.lang == lang)
    )
    row = session.exec(stmt).first()
    if row:
        changed = False
        if not row.enabled:
            row.enabled = True
            changed = True
        if float(row.weight) != float(weight):
            row.weight = float(weight)
            changed = True
        if int(row.window_1) != int(window_1):
            row.window_1 = int(window_1)
            changed = True
        if int(row.window_2) != int(window_2):
            row.window_2 = int(window_2)
            changed = True
        if changed:
            session.add(row)
        return changed

    session.add(
        ContextTerm(
            rule_set_id=rule_set_id,
            entity_type=entity_type,
            term=term,
            lang=lang,
            weight=float(weight),
            window_1=int(window_1),
            window_2=int(window_2),
            enabled=True,
        )
    )
    return True


def main() -> None:
    inserted_or_updated = 0

    with Session(engine) as session:
        for entity_type, terms in BASE_ENTITY_TERMS.items():
            for raw in terms:
                term = _normalize(raw)
                if not term:
                    continue
                if _upsert_term(
                    session=session,
                    rule_set_id=None,
                    entity_type=entity_type,
                    term=term,
                    lang="vi",
                    weight=1.0,
                    window_1=60,
                    window_2=20,
                ):
                    inserted_or_updated += 1

        for entity_type, term in _iter_persona_terms_from_yaml():
            if _upsert_term(
                session=session,
                rule_set_id=None,
                entity_type=entity_type,
                term=term,
                lang="vi",
                weight=1.0,
                window_1=60,
                window_2=20,
            ):
                inserted_or_updated += 1

        session.commit()

    print(f"[seed_context_terms] upserted={inserted_or_updated}")


if __name__ == "__main__":
    main()

