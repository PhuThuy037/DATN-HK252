from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Protocol


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


class LangAdapter(Protocol):
    lang: str

    def word_to_digit(self, w: str) -> Optional[str]: ...

    def is_multiplier(self, w: str) -> int: ...

    def is_filler(self, w: str) -> bool: ...


_WORD_RE = re.compile(r"[^\W\d_]+|\d+", re.UNICODE)


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    for match in _WORD_RE.finditer(text):
        tokens.append(Token(match.group(0), match.start(), match.end()))
    return tokens


class VietnameseAdapter:
    lang = "vi"

    _map = {
        "khong": "0",
        "ko": "0",
        "mot": "1",
        "hai": "2",
        "ba": "3",
        "bon": "4",
        "tu": "4",
        "nam": "5",
        "sau": "6",
        "bay": "7",
        "tam": "8",
        "chin": "9",
    }

    _fillers = {
        "la",
        "cua",
        "toi",
        "so",
        "dien",
        "thoai",
        "cccd",
        "can",
        "cuoc",
        "mst",
        "ma",
        "thue",
    }

    def word_to_digit(self, w: str) -> Optional[str]:
        return self._map.get(w)

    def is_multiplier(self, w: str) -> int:
        return 1

    def is_filler(self, w: str) -> bool:
        return w in self._fillers


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

    _fillers = {"my", "number", "phone", "is", "the", "of", "tax", "id", "code"}

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


class DigitNormalizer:
    def __init__(self):
        self.adapters = [VietnameseAdapter(), EnglishAdapter()]

    def extract(self, text: str) -> List[NumberCandidate]:
        tokens = tokenize(text)
        results: List[NumberCandidate] = []

        for adapter in self.adapters:
            results.extend(self._extract_with_adapter(tokens=tokens, adapter=adapter))

        return results

    def _extract_with_adapter(
        self,
        *,
        tokens: List[Token],
        adapter: LangAdapter,
    ) -> List[NumberCandidate]:
        candidates: List[NumberCandidate] = []
        i = 0
        while i < len(tokens):
            start_token = tokens[i]
            folded = self._fold_token(start_token.text)
            digit = adapter.word_to_digit(folded)

            if not (digit or folded.isdigit()):
                i += 1
                continue

            start = start_token.start
            digits = ""
            j = i

            while j < len(tokens):
                current = tokens[j]
                current_folded = self._fold_token(current.text)

                mul = adapter.is_multiplier(current_folded)
                if mul > 1 and j + 1 < len(tokens):
                    next_folded = self._fold_token(tokens[j + 1].text)
                    next_digit = adapter.word_to_digit(next_folded)
                    if next_digit:
                        digits += next_digit * mul
                        j += 2
                        continue

                mapped = adapter.word_to_digit(current_folded)
                if mapped:
                    digits += mapped
                    j += 1
                    continue

                if current_folded.isdigit():
                    digits += current_folded
                    j += 1
                    continue

                if adapter.is_filler(current_folded):
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

        return candidates

    def _fold_token(self, word: str) -> str:
        raw = str(word or "").lower().replace("\u0111", "d")
        normalized = unicodedata.normalize("NFKD", raw)
        return "".join(ch for ch in normalized if not unicodedata.combining(ch))
