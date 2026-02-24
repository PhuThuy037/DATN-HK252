from __future__ import annotations

from typing import Any, List
from dataclasses import dataclass

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.common.enums import EntitySource


@dataclass(slots=True)
class Entity:
    type: str
    start: int
    end: int
    score: float
    source: str
    text: str
    metadata: dict[str, Any]


class PresidioDetector:
    """
    Presidio wrapper.
    Chỉ dùng cho PII quốc tế (email, credit card, ssn...)
    """

    TYPE_MAP = {
        "EMAIL_ADDRESS": "EMAIL",
        "PHONE_NUMBER": "PHONE",
        "CREDIT_CARD": "CREDIT_CARD",
        "IP_ADDRESS": "IP",
        "URL": "URL",
        "US_SSN": "SSN",
    }

    def __init__(self) -> None:
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": "en", "model_name": "en_core_web_sm"},
            ],
        }

        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()

        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)

    def scan(self, text: str, language: str = "en") -> List[Entity]:
        results = self.analyzer.analyze(text=text, language=language)

        entities: list[Entity] = []

        for r in results:
            mapped_type = self.TYPE_MAP.get(r.entity_type)
            if not mapped_type:
                continue  # bỏ những thứ linh tinh

            entities.append(
                Entity(
                    type=mapped_type,
                    start=r.start,
                    end=r.end,
                    score=float(r.score),
                    source=EntitySource.presidio.value,
                    text=text[r.start : r.end],
                    metadata={},
                )
            )

        return entities