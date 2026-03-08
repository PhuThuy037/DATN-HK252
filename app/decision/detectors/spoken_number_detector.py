from __future__ import annotations

from typing import List

from app.decision.detectors.local_regex_detector import Entity
from app.decision.normalizers.digit_normalizer import DigitNormalizer


class SpokenNumberDetector:
    """
    Detect numbers written as words (vi/en) -> produce PHONE / CCCD / TAX_ID candidates.

    MVP:
    - digit words only
    - double/triple supported
    - context boost
    """

    def __init__(self):
        self.norm = DigitNormalizer()

        # Context keywords (simple MVP)
        self.KW_PHONE = ["sđt", "số điện thoại", "điện thoại", "hotline", "liên hệ"]
        self.KW_CCCD = ["cccd", "căn cước", "căn cước công dân", "cmnd"]
        self.KW_TAX = ["mst", "mã số thuế", "tax code", "tax id"]

    def scan(self, text: str) -> List[Entity]:
        candidates = self.norm.extract(text)
        results: List[Entity] = []

        lower_text = (text or "").lower()

        for c in candidates:
            digits = c.digits
            n = len(digits)

            etype = self._guess_type(
                digits=digits,
                lower_text=lower_text,
                start=c.start,
            )
            if not etype:
                continue

            # Spoken numbers are less certain than regex
            base_score = float(c.confidence)

            # context boost
            context_level = self._context_level(lower_text, c.start, etype)
            if context_level == 2:
                score = min(0.95, base_score + 0.15)
            elif context_level == 1:
                score = min(0.90, base_score + 0.08)
            else:
                score = max(0.70, base_score)

            # ✅ FIX HERE: expand end to swallow remaining letters (vd "bả" + "y" => "bảy")
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
                        "length": n,
                        "context_level": context_level,
                    },
                )
            )

        return results

    # ------------------------------------------------
    # Type guessing
    # ------------------------------------------------

    def _guess_type(self, digits: str, *, lower_text: str, start: int) -> str | None:
        n = len(digits)
        ctx = self._context_window(lower_text, start, 60)

        has_cccd_ctx = any(k in ctx for k in self.KW_CCCD)
        has_tax_ctx = any(k in ctx for k in self.KW_TAX)

        # Favor explicit context for office identifiers.
        if n in (12, 13) and has_cccd_ctx:
            return "CCCD"

        # Strong by length (default fallback)
        if n == 12:
            return "CCCD"
        if n == 13:
            return "TAX_ID"

        # Ambiguous length 10
        if n == 10:
            if has_tax_ctx:
                return "TAX_ID"
            if any(k in ctx for k in self.KW_PHONE):
                return "PHONE"

            # default VN: 10 digits -> phone
            return "PHONE"

        # Phone-like lengths
        if n in (9, 11):
            return "PHONE"

        return None

    # ------------------------------------------------
    # Context scoring
    # ------------------------------------------------

    def _context_level(self, text: str, pos: int, etype: str) -> int:
        """
        0 = no context
        1 = keyword within ±60
        2 = keyword within ±20
        """
        if etype == "PHONE":
            keywords = self.KW_PHONE
        elif etype == "CCCD":
            keywords = self.KW_CCCD
        elif etype == "TAX_ID":
            keywords = self.KW_TAX
        else:
            return 0

        for window, level in [(20, 2), (60, 1)]:
            s = max(0, pos - window)
            e = min(len(text), pos + window)
            snippet = text[s:e]
            if any(k in snippet for k in keywords):
                return level
        return 0

    def _context_window(self, text: str, pos: int, window: int) -> str:
        s = max(0, pos - window)
        e = min(len(text), pos + window)
        return text[s:e]

    def _expand_end(self, text: str, end: int) -> int:
        # ăn tiếp các ký tự chữ của từ cuối (vd "bả" + "y" => "bảy")
        n = len(text)
        while end < n and text[end].isalpha():
            end += 1
        return end
