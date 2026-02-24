from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


# -----------------------------------
# Unified Entity Model
# -----------------------------------


@dataclass(slots=True)
class Entity:
    type: str
    start: int
    end: int
    score: float
    source: str
    text: str
    metadata: dict


# -----------------------------------
# Local VN Regex Detector
# -----------------------------------


class LocalRegexDetector:
    EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")

    PHONE_PATTERN = re.compile(r"\b(?:\+84|0)(?:[\s.\-]?\d){9,10}\b")

    CCCD_PATTERN = re.compile(r"\b\d{12}\b")

    TAX_ID_PATTERN = re.compile(r"\b\d{10}(?:-\d{3})?\b")

    API_SECRET_PATTERNS = [
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"),
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    ]

    CCCD_CONTEXT = ["cccd", "căn cước", "cmnd"]
    TAX_CONTEXT = ["mst", "mã số thuế", "tax code"]
    PHONE_CONTEXT = ["sđt", "số điện thoại", "hotline", "liên hệ", "số"]

    def scan(self, text: str) -> List[Entity]:
        entities: List[Entity] = []
        lower_text = text.lower()

        # EMAIL
        for m in self.EMAIL_PATTERN.finditer(text):
            entities.append(
                Entity(
                    type="EMAIL",
                    start=m.start(),
                    end=m.end(),
                    score=0.95,
                    source="local_regex",
                    text=m.group(),
                    metadata={"normalized": m.group().lower()},
                )
            )

        # PHONE
        for m in self.PHONE_PATTERN.finditer(text):
            normalized = self._normalize_phone(m.group())
            context_level = self._context_level(
                lower_text, m.start(), self.PHONE_CONTEXT
            )
            score = 0.90 if context_level == 2 else 0.80 if context_level == 1 else 0.70

            entities.append(
                Entity(
                    type="PHONE",
                    start=m.start(),
                    end=m.end(),
                    score=score,
                    source="local_regex",
                    text=m.group(),
                    metadata={
                        "normalized": normalized,
                        "context_level": context_level,
                    },
                )
            )

        # CCCD
        for m in self.CCCD_PATTERN.finditer(text):
            context_level = self._context_level(
                lower_text, m.start(), self.CCCD_CONTEXT
            )
            score = 0.95 if context_level == 2 else 0.85 if context_level == 1 else 0.65

            entities.append(
                Entity(
                    type="CCCD",
                    start=m.start(),
                    end=m.end(),
                    score=score,
                    source="local_regex",
                    text=m.group(),
                    metadata={"context_level": context_level},
                )
            )

        # TAX ID
        for m in self.TAX_ID_PATTERN.finditer(text):
            context_level = self._context_level(lower_text, m.start(), self.TAX_CONTEXT)
            score = 0.90 if context_level == 2 else 0.80 if context_level == 1 else 0.65

            entities.append(
                Entity(
                    type="TAX_ID",
                    start=m.start(),
                    end=m.end(),
                    score=score,
                    source="local_regex",
                    text=m.group(),
                    metadata={
                        "normalized": m.group().replace("-", ""),
                        "context_level": context_level,
                    },
                )
            )

        # API SECRET
        for pattern in self.API_SECRET_PATTERNS:
            for m in pattern.finditer(text):
                entities.append(
                    Entity(
                        type="API_SECRET",
                        start=m.start(),
                        end=m.end(),
                        score=0.98,
                        source="local_regex",
                        text=m.group(),
                        metadata={},
                    )
                )

        return entities

    # -----------------------------------
    # Helpers
    # -----------------------------------

    def _normalize_phone(self, phone: str) -> str:
        digits = re.sub(r"[^\d]", "", phone)
        if digits.startswith("84"):
            digits = "0" + digits[2:]
        return digits

    def _context_level(self, text: str, pos: int, keywords: List[str]) -> int:
        """
        0 = no context
        1 = keyword within ±60
        2 = keyword within ±20
        """
        for window, level in [(20, 2), (60, 1)]:
            start = max(0, pos - window)
            end = min(len(text), pos + window)
            snippet = text[start:end]
            if any(k in snippet for k in keywords):
                return level
        return 0