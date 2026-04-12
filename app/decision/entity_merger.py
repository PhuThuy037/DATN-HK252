from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from app.decision.entity_priority import entity_precedence_key


def _score(e) -> float:
    return float(getattr(e, "score", 0.0) or 0.0)


def _start(e) -> int:
    return int(getattr(e, "start", 0) or 0)


def _end(e) -> int:
    return int(getattr(e, "end", 0) or 0)


def _etype(e) -> str:
    return str(getattr(e, "entity_type", None) or getattr(e, "type", "") or "")


def _source(e) -> str:
    return str(getattr(e, "source", "") or "")


def _metadata(e) -> dict:
    data = getattr(e, "metadata", None)
    return data if isinstance(data, dict) else {}


def _context_level(e) -> int:
    try:
        return int(_metadata(e).get("context_level", 0) or 0)
    except Exception:
        return 0


def _overlap_ratio(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    inter = max(0, min(a_end, b_end) - max(a_start, b_start))
    if inter <= 0:
        return 0.0
    len_a = max(1, a_end - a_start)
    len_b = max(1, b_end - b_start)
    return inter / float(min(len_a, len_b))


@dataclass(slots=True)
class MergeConfig:
    overlap_threshold: float = 0.80
    prefer_source_order: tuple[str, ...] = ("local_regex", "presidio")


class EntityMerger:
    """
    Merge entities from multiple detectors and resolve strong overlaps.
    """

    def __init__(self, config: Optional[MergeConfig] = None):
        self.cfg = config or MergeConfig()

    def merge(self, entities: Iterable) -> List:
        items = [e for e in entities if e is not None]
        if not items:
            return []

        items.sort(key=lambda e: (_start(e), -_end(e), -_score(e)))

        merged: list = []
        for entity in items:
            if not merged:
                merged.append(entity)
                continue

            last = merged[-1]
            same_type = _etype(entity) == _etype(last) and _etype(entity) != ""
            ratio = _overlap_ratio(
                _start(entity),
                _end(entity),
                _start(last),
                _end(last),
            )

            if ratio >= self.cfg.overlap_threshold:
                merged[-1] = self._resolve_overlap(entity, last, same_type=same_type)
                continue

            merged.append(entity)

        return merged

    def _resolve_overlap(self, a, b, *, same_type: bool):
        if same_type:
            score_a = _score(a)
            score_b = _score(b)
            if score_a > score_b:
                return a
            if score_b > score_a:
                return b
            return self._prefer(a, b)

        ambiguous_pair = {_etype(a), _etype(b)}
        if ambiguous_pair == {"PHONE", "TAX_ID"}:
            resolved = self._resolve_phone_tax_overlap(a, b)
            if resolved is not None:
                return resolved

        key_a = entity_precedence_key(a)
        key_b = entity_precedence_key(b)
        if key_a > key_b:
            return a
        if key_b > key_a:
            return b
        return self._prefer(a, b)

    def _resolve_phone_tax_overlap(self, a, b):
        score_a = _score(a)
        score_b = _score(b)
        if score_a > score_b:
            return a
        if score_b > score_a:
            return b

        context_a = _context_level(a)
        context_b = _context_level(b)
        if context_a > context_b:
            return a
        if context_b > context_a:
            return b
        return None

    def _prefer(self, a, b):
        order = {source: index for index, source in enumerate(self.cfg.prefer_source_order)}
        rank_a = order.get(_source(a), 999)
        rank_b = order.get(_source(b), 999)
        return a if rank_a < rank_b else b
