from __future__ import annotations

from typing import Any


_ENTITY_PRIORITY: dict[str, int] = {
    "API_SECRET": 100,
    "CUSTOM_SECRET": 95,
    "CREDIT_CARD": 90,
    "CCCD": 85,
    "TAX_ID": 80,
    "EMAIL": 70,
    "PHONE": 60,
    "ADDRESS": 50,
}

_SOURCE_PRIORITY: dict[str, int] = {
    "local_regex": 40,
    "vn_address": 35,
    "spoken_email": 30,
    "spoken_norm": 25,
    "presidio": 20,
}


def entity_type_priority(entity_type: str | None) -> int:
    return _ENTITY_PRIORITY.get(str(entity_type or "").strip().upper(), 0)


def source_priority(source: str | None) -> int:
    return _SOURCE_PRIORITY.get(str(source or "").strip(), 0)


def entity_precedence_key(entity: Any) -> tuple[int, int, float, int]:
    start = int(getattr(entity, "start", 0) or 0)
    end = int(getattr(entity, "end", 0) or 0)
    score = float(getattr(entity, "score", 0.0) or 0.0)
    entity_type = getattr(entity, "entity_type", None) or getattr(entity, "type", "")
    source = getattr(entity, "source", "")
    return (
        entity_type_priority(str(entity_type)),
        max(0, end - start),
        score,
        source_priority(str(source)),
    )
