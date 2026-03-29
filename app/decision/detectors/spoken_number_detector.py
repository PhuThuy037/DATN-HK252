from __future__ import annotations

import re
import unicodedata
from typing import List

from app.decision.detectors.local_regex_detector import Entity
from app.decision.normalizers.digit_normalizer import DigitNormalizer


class SpokenNumberDetector:
    """
    Detect numbers written as words (vi/en) and emit PHONE / CCCD / TAX_ID entities.
    """

    def __init__(self):
        self.norm = DigitNormalizer()

        # Use folded ASCII keywords for stable matching across accent variants.
        self.KW_PHONE = [
            "sdt",
            "so dien thoai",
            "dien thoai",
            "hotline",
            "lien he",
            "phone",
        ]
        self.KW_CCCD = [
            "cccd",
            "can cuoc",
            "can cuoc cong dan",
            "cmnd",
        ]
        # Keep TAX_ID context strict to reduce false positives for generic numeric text.
        self.KW_TAX_STRONG = [
            "ma so thue",
            "mst",
            "tax id",
            "tax code",
            "taxpayer id",
            "tin",
        ]

    def scan(self, text: str) -> List[Entity]:
        candidates = self.norm.extract(text)
        results: List[Entity] = []
        lower_text = str(text or "").lower()

        for c in candidates:
            digits = c.digits
            etype = self._guess_type(
                digits=digits,
                lower_text=lower_text,
                start=int(c.start),
            )
            if not etype:
                continue

            base_score = float(c.confidence)
            context_level = self._context_level(lower_text, int(c.start), etype)
            if context_level == 2:
                score = min(0.95, base_score + 0.15)
            elif context_level == 1:
                score = min(0.90, base_score + 0.08)
            else:
                score = max(0.70, base_score)

            start = int(c.start)
            end = self._expand_end(text, int(c.end))
            results.append(
                Entity(
                    type=etype,
                    start=start,
                    end=end,
                    score=score,
                    source="spoken_norm",
                    text=text[start:end],
                    metadata={
                        "normalized": digits,
                        "lang": c.lang,
                        "length": len(digits),
                        "context_level": context_level,
                    },
                )
            )

        return results

    def _guess_type(self, digits: str, *, lower_text: str, start: int) -> str | None:
        n = len(digits)
        ctx = self._context_window(lower_text, start, 60)

        has_cccd_ctx = any(k in ctx for k in self.KW_CCCD)
        has_tax_ctx = any(k in ctx for k in self.KW_TAX_STRONG)
        has_phone_ctx = any(k in ctx for k in self.KW_PHONE)

        if n in (12, 13) and has_cccd_ctx:
            return "CCCD"

        if n == 12:
            return "CCCD"

        # Tax id remains context-gated (strict) to avoid classifying random numbers as TAX_ID.
        if n == 13:
            return "TAX_ID" if has_tax_ctx else None

        if n == 10:
            if has_tax_ctx:
                return "TAX_ID"
            if has_phone_ctx:
                return "PHONE"
            # VN default for ambiguous 10-digit spoken sequence.
            return "PHONE"

        if n in (9, 11):
            return "PHONE"

        return None

    def _context_level(self, text: str, pos: int, etype: str) -> int:
        """
        0 = no context
        1 = keyword within +-60 chars
        2 = keyword within +-20 chars
        """
        if etype == "PHONE":
            keywords = self.KW_PHONE
        elif etype == "CCCD":
            keywords = self.KW_CCCD
        elif etype == "TAX_ID":
            keywords = self.KW_TAX_STRONG
        else:
            return 0

        for window, level in ((20, 2), (60, 1)):
            snippet = self._context_window(text, pos, window)
            if any(k in snippet for k in keywords):
                return level
        return 0

    def _context_window(self, text: str, pos: int, window: int) -> str:
        start = max(0, int(pos) - int(window))
        end = min(len(text), int(pos) + int(window))
        return self._fold_text(text[start:end])

    def _fold_text(self, text: str) -> str:
        raw = str(text or "").lower().replace("\u0111", "d")
        normalized = unicodedata.normalize("NFKD", raw)
        no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        no_symbols = re.sub(r"[^a-z0-9\s:/._-]+", " ", no_marks)
        return re.sub(r"\s+", " ", no_symbols).strip()

    def _expand_end(self, text: str, end: int) -> int:
        # Extend end index to include trailing alphabetic chars in partially-tokenized words.
        n = len(text)
        cursor = int(end)
        while cursor < n and text[cursor].isalpha():
            cursor += 1
        return cursor
