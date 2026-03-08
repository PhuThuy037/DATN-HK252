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


@dataclass(slots=True, frozen=True)
class ContextHint:
    term: str
    window_1: int = 60
    window_2: int = 20
    weight: float = 1.0


# -----------------------------------
# Local VN Regex Detector
# -----------------------------------


class LocalRegexDetector:
    EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")

    PHONE_PATTERN = re.compile(r"\b(?:\+84|0)(?:[\s.\-]?\d){9,10}\b")

    CCCD_PATTERN = re.compile(r"\b\d{12}\b")

    TAX_ID_PATTERN = re.compile(r"\b\d{10}(?:-\d{3})?\b")
    CREDIT_CARD_CANDIDATE_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

    API_SECRET_PATTERNS = [
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"),
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    ]

    # Keep ASCII-safe defaults; DB-backed context_terms is preferred in runtime.
    CCCD_CONTEXT = ["cccd", "can cuoc", "cmnd"]
    TAX_CONTEXT = ["mst", "ma so thue", "tax code"]
    PHONE_CONTEXT = ["sdt", "so dien thoai", "hotline", "lien he", "so"]

    DEFAULT_CONTEXT_HINTS: dict[str, list[ContextHint]] = {
        "PHONE": [ContextHint(term=t) for t in PHONE_CONTEXT],
        "CCCD": [ContextHint(term=t) for t in CCCD_CONTEXT],
        "TAX_ID": [ContextHint(term=t) for t in TAX_CONTEXT],
    }

    def scan(
        self,
        text: str,
        *,
        context_hints_by_entity: dict[str, list[ContextHint]] | None = None,
    ) -> List[Entity]:
        entities: List[Entity] = []
        lower_text = (text or "").lower()
        hints = self._resolve_context_hints(context_hints_by_entity)

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
            context_level = self._context_level(lower_text, m.start(), hints["PHONE"])
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
            context_level = self._context_level(lower_text, m.start(), hints["CCCD"])
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
            context_level = self._context_level(lower_text, m.start(), hints["TAX_ID"])
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

        # CREDIT CARD
        for m in self.CREDIT_CARD_CANDIDATE_PATTERN.finditer(text):
            raw_value = m.group()
            digits = re.sub(r"[^\d]", "", raw_value)
            if len(digits) < 13 or len(digits) > 19:
                continue
            if not self._is_valid_credit_card_number(digits):
                continue

            entities.append(
                Entity(
                    type="CREDIT_CARD",
                    start=m.start(),
                    end=m.end(),
                    score=0.92,
                    source="local_regex",
                    text=raw_value,
                    metadata={"normalized": digits, "last4": digits[-4:]},
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

    def _is_valid_credit_card_number(self, digits: str) -> bool:
        total = 0
        reverse_digits = digits[::-1]
        for idx, ch in enumerate(reverse_digits):
            n = int(ch)
            if idx % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return total % 10 == 0

    def _normalize_phone(self, phone: str) -> str:
        digits = re.sub(r"[^\d]", "", phone)
        if digits.startswith("84"):
            digits = "0" + digits[2:]
        return digits

    def _resolve_context_hints(
        self,
        context_hints_by_entity: dict[str, list[ContextHint]] | None,
    ) -> dict[str, list[ContextHint]]:
        resolved: dict[str, list[ContextHint]] = {
            "PHONE": list(self.DEFAULT_CONTEXT_HINTS["PHONE"]),
            "CCCD": list(self.DEFAULT_CONTEXT_HINTS["CCCD"]),
            "TAX_ID": list(self.DEFAULT_CONTEXT_HINTS["TAX_ID"]),
        }
        if not context_hints_by_entity:
            return resolved

        for et in ("PHONE", "CCCD", "TAX_ID"):
            incoming = context_hints_by_entity.get(et) or []
            if incoming:
                resolved[et] = incoming
        return resolved

    def _context_level(self, text: str, pos: int, hints: List[ContextHint]) -> int:
        """
        0 = no context
        1 = keyword within +/- window_1
        2 = keyword within +/- window_2
        """
        if not hints:
            return 0

        # Stronger window first.
        for hint in hints:
            term = (hint.term or "").strip().lower()
            if not term:
                continue
            w2 = max(1, int(hint.window_2))
            start = max(0, pos - w2)
            end = min(len(text), pos + w2)
            if term in text[start:end]:
                return 2

        for hint in hints:
            term = (hint.term or "").strip().lower()
            if not term:
                continue
            w1 = max(1, int(hint.window_1))
            start = max(0, pos - w1)
            end = min(len(text), pos + w1)
            if term in text[start:end]:
                return 1

        return 0
