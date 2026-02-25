# app/decision/detectors/presidio_detector.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import SpacyNlpEngine


@dataclass(slots=True)
class Entity:
    type: str
    start: int
    end: int
    score: float
    source: str = "presidio"
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class PresidioDetector:
    # ✅ loại nhiễu phổ biến
    DEFAULT_DROP_TYPES = {
        "DATE_TIME",  # hay ăn ké số
        "URL",  # hay ăn ké domain trong email
    }

    def __init__(
        self,
        *,
        model_name: str = "en_core_web_sm",
        drop_types: Iterable[str] | None = None,
        min_score: float = 0.5,
    ):
        nlp_engine = SpacyNlpEngine(
            models=[{"lang_code": "en", "model_name": model_name}]
        )
        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)

        self.drop_types = (
            set(drop_types) if drop_types is not None else set(self.DEFAULT_DROP_TYPES)
        )
        self.min_score = float(min_score)

    def scan(self, text: str) -> List[Entity]:
        results = self.analyzer.analyze(text=text, language="en")
        out: list[Entity] = []

        for r in results:
            et = str(r.entity_type)

            if et in self.drop_types:
                continue

            if float(r.score) < self.min_score:
                continue

            frag = text[r.start : r.end]
            out.append(
                Entity(
                    type=et,
                    start=int(r.start),
                    end=int(r.end),
                    score=float(r.score),
                    source="presidio",
                    text=frag,
                    metadata={},
                )
            )

        return out