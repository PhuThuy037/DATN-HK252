from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


def _score(e) -> float:
    return float(getattr(e, "score", 0.0) or 0.0)


def _start(e) -> int:
    return int(getattr(e, "start", 0) or 0)


def _end(e) -> int:
    return int(getattr(e, "end", 0) or 0)


def _etype(e) -> str:
    # entity_type hoặc type
    return str(getattr(e, "entity_type", None) or getattr(e, "type", "") or "")


def _source(e) -> str:
    return str(getattr(e, "source", "") or "")


def _overlap_ratio(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    # IoU-lite: overlap / min(lenA, lenB)
    inter = max(0, min(a_end, b_end) - max(a_start, b_start))
    if inter <= 0:
        return 0.0
    len_a = max(1, a_end - a_start)
    len_b = max(1, b_end - b_start)
    return inter / float(min(len_a, len_b))


@dataclass(slots=True)
class MergeConfig:
    overlap_threshold: float = 0.80
    # Nếu score bằng nhau, ưu tiên source nào?
    prefer_source_order: tuple[str, ...] = ("local_regex", "presidio")


class EntityMerger:
    """
    Merge entities từ nhiều detector (Local + Presidio) để:
      - không duplicate (cùng type + overlap cao)
      - giữ best candidate (score cao hơn, hoặc ưu tiên source)
    """

    def __init__(self, config: Optional[MergeConfig] = None):
        self.cfg = config or MergeConfig()

    def merge(self, entities: Iterable) -> List:
        items = [e for e in entities if e is not None]
        if not items:
            return []

        # sort theo start asc, end desc, score desc
        items.sort(key=lambda e: (_start(e), -_end(e), -_score(e)))

        merged: list = []
        for e in items:
            if not merged:
                merged.append(e)
                continue

            last = merged[-1]

            same_type = _etype(e) == _etype(last) and _etype(e) != ""
            ratio = _overlap_ratio(_start(e), _end(e), _start(last), _end(last))

            if same_type and ratio >= self.cfg.overlap_threshold:
                # chọn winner
                e_score = _score(e)
                last_score = _score(last)

                if e_score > last_score:
                    merged[-1] = e
                elif e_score == last_score:
                    # tie-breaker theo source preference
                    merged[-1] = self._prefer(e, last)
                # else giữ last
            else:
                merged.append(e)

        return merged

    def _prefer(self, a, b):
        order = {s: i for i, s in enumerate(self.cfg.prefer_source_order)}
        ra = order.get(_source(a), 999)
        rb = order.get(_source(b), 999)
        return a if ra < rb else b