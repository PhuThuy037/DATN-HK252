from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, List, Protocol


# =========================
# Models
# =========================


@dataclass(slots=True)
class Token:
    text: str
    start: int
    end: int


@dataclass(slots=True)
class NumberCandidate:
    start: int
    end: int
    digits: str
    confidence: float
    lang: str
    meta: dict


# =========================
# Adapter Interface
# =========================


class LangAdapter(Protocol):
    lang: str

    def word_to_digit(self, w: str) -> Optional[str]: ...

    def is_multiplier(self, w: str) -> int: ...

    def is_filler(self, w: str) -> bool: ...


# =========================
# Tokenizer
# =========================

_WORD_RE = re.compile(r"[A-Za-zÀ-ỹ]+|\d+")


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    for m in _WORD_RE.finditer(text):
        tokens.append(Token(m.group(0), m.start(), m.end()))
    return tokens


# =========================
# Vietnamese Adapter
# =========================


class VietnameseAdapter:
    lang = "vi"

    _map = {
        "không": "0",
        "khong": "0",
        "ko": "0",
        "một": "1",
        "mot": "1",
        "hai": "2",
        "ba": "3",
        "bốn": "4",
        "bon": "4",
        "tư": "4",
        "tu": "4",
        "năm": "5",
        "nam": "5",
        "sáu": "6",
        "sau": "6",
        "bảy": "7",
        "bay": "7",
        "tám": "8",
        "tam": "8",
        "chín": "9",
        "chin": "9",
    }

    _fillers = {
        "là",
        "của",
        "tôi",
        "toi",
        "số",
        "dien",
        "điện",
        "thoại",
        "thoai",
        "cccd",
        "căn",
        "cước",
    }

    def word_to_digit(self, w: str) -> Optional[str]:
        return self._map.get(w)

    def is_multiplier(self, w: str) -> int:
        return 1  # VI không xử lý double/triple

    def is_filler(self, w: str) -> bool:
        return w in self._fillers


# =========================
# English Adapter
# =========================


class EnglishAdapter:
    lang = "en"

    _map = {
        "zero": "0",
        "oh": "0",
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
    }

    _fillers = {"my", "number", "phone", "is", "the", "of"}

    def word_to_digit(self, w: str) -> Optional[str]:
        return self._map.get(w)

    def is_multiplier(self, w: str) -> int:
        if w == "double":
            return 2
        if w == "triple":
            return 3
        return 1

    def is_filler(self, w: str) -> bool:
        return w in self._fillers


# =========================
# Normalizer Engine
# =========================


class DigitNormalizer:
    def __init__(self):
        self.adapters = [
            VietnameseAdapter(),
            EnglishAdapter(),
        ]

    def extract(self, text: str) -> List[NumberCandidate]:
        tokens = tokenize(text)
        results: List[NumberCandidate] = []

        for adapter in self.adapters:
            results.extend(self._extract_with_adapter(text, tokens, adapter))

        return results

    def _extract_with_adapter(
        self,
        text: str,
        tokens: List[Token],
        adapter: LangAdapter,
    ) -> List[NumberCandidate]:

        candidates: List[NumberCandidate] = []

        i = 0
        while i < len(tokens):
            t = tokens[i]
            w = t.text.lower()

            digit = adapter.word_to_digit(w)
            multiplier = adapter.is_multiplier(w)

            if digit or w.isdigit():
                start = t.start
                digits = ""
                j = i

                while j < len(tokens):
                    current = tokens[j]
                    cw = current.text.lower()

                    # multiplier (EN)
                    mul = adapter.is_multiplier(cw)
                    if mul > 1 and j + 1 < len(tokens):
                        next_word = tokens[j + 1].text.lower()
                        next_digit = adapter.word_to_digit(next_word)
                        if next_digit:
                            digits += next_digit * mul
                            j += 2
                            continue

                    # direct digit word
                    d = adapter.word_to_digit(cw)
                    if d:
                        digits += d
                        j += 1
                        continue

                    # raw numeric
                    if cw.isdigit():
                        digits += cw
                        j += 1
                        continue

                    # filler
                    if adapter.is_filler(cw):
                        j += 1
                        continue

                    break

                if len(digits) >= 6:
                    end = tokens[j - 1].end
                    candidates.append(
                        NumberCandidate(
                            start=start,
                            end=end,
                            digits=digits,
                            confidence=min(0.99, 0.6 + len(digits) * 0.02),
                            lang=adapter.lang,
                            meta={"length": len(digits)},
                        )
                    )

                i = j
            else:
                i += 1

        return candidates

