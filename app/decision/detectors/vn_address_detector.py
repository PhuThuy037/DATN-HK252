from __future__ import annotations

import re
import unicodedata
from typing import List

from app.decision.detectors.folded_text import (
    fold_text_with_mapping,
    original_span_from_folded,
)
from app.decision.detectors.local_regex_detector import Entity


class VietnameseAddressDetector:
    _INLINE_WS = r"[ \t]+"
    _OPT_INLINE_WS = r"[ \t]*"
    _SEP = rf"(?:\s*,\s*|{_INLINE_WS})"
    _HOUSE_NUMBER = r"\d{1,5}[a-z]?(?:/\d{1,4}[a-z]?)?"
    _HOUSE_LABEL = rf"(?:(?:so\.?|nha){_INLINE_WS})?"
    _ALLEY = rf"(?:(?:ngo|ngach|hem){_INLINE_WS}{_HOUSE_NUMBER})"
    _STREET_NAME = rf"[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{1,6}}"
    _STREET_MARKER = rf"(?:(?:duong|pho){_INLINE_WS})?"
    _HOUSE_STREET = (
        rf"{_HOUSE_LABEL}{_HOUSE_NUMBER}"
        rf"(?:{_SEP}{_ALLEY})?"
        rf"(?:{_SEP}{_STREET_MARKER}{_STREET_NAME}|{_INLINE_WS}{_STREET_NAME})"
    )
    _WARD_MARKER = (
        rf"(?:phuong|xa|thi{_INLINE_WS}tran|p\b\.?|x\b\.?|tt\b\.?)"
    )
    _WARD = (
        rf"{_WARD_MARKER}{_INLINE_WS}[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{0,3}}"
    )
    _DISTRICT = (
        rf"(?:(?:quan|q\b\.?){_OPT_INLINE_WS}"
        rf"(?:\d{{1,2}}|[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{0,3}})|"
        rf"(?:huyen|thi{_INLINE_WS}xa|tx\b\.?){_INLINE_WS}"
        rf"[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{0,3}})"
    )
    _DISTRICT_PLAIN = r"(?:binh thanh|thu duc|go vap|tan binh|tan phu|phu nhuan|binh tan)"
    _DISTRICT_ANY = rf"(?:{_DISTRICT}|{_DISTRICT_PLAIN})"
    _CITY_PLAIN = (
        r"(?:ha noi|ho chi minh|da nang|hai phong|can tho|hue|"
        r"ba ria vung tau|quang ninh|nghe an|thanh hoa)"
    )
    _CITY = (
        rf"(?:tp\.?{_OPT_INLINE_WS}[a-z0-9.]+|thanh{_INLINE_WS}pho{_INLINE_WS}"
        rf"[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{0,3}}|"
        rf"tinh{_INLINE_WS}[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{0,3}}|"
        rf"{_CITY_PLAIN})"
    )
    _BUILDING = (
        rf"(?:(?:tang{_OPT_INLINE_WS}\d+[a-z]?\s*,\s*(?:toa{_INLINE_WS}nha{_INLINE_WS}"
        rf"[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{0,4}}\s*,\s*)?)|"
        rf"(?:toa{_INLINE_WS}nha{_INLINE_WS}[a-z0-9]+"
        rf"(?:{_INLINE_WS}[a-z0-9]+){{0,4}}\s*,\s*))"
    )
    _ROOM = rf"phong{_OPT_INLINE_WS}[a-z0-9]+(?:/[a-z0-9]+)?"
    _HOUSE_BLOCK = rf"nha{_OPT_INLINE_WS}[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{0,2}}"
    _NEIGHBORHOOD = (
        rf"khu{_INLINE_WS}pho{_OPT_INLINE_WS}[a-z0-9]+"
        rf"(?:{_INLINE_WS}[a-z0-9]+){{0,2}}"
    )
    _WARD_PLAIN = r"(?:linh trung|linh tay|linh xuan|ben nghe|ben thanh)"
    _WARD_ANY = rf"(?:{_WARD}|{_WARD_PLAIN})"
    _FULL_PATTERN = re.compile(
        rf"(?P<address>{_HOUSE_STREET}{_SEP}{_WARD}{_SEP}{_DISTRICT}{_SEP}{_CITY})",
        flags=re.IGNORECASE,
    )
    _SHORT_PATTERN = re.compile(
        rf"(?P<address>{_HOUSE_STREET}{_SEP}{_DISTRICT}{_SEP}{_CITY})",
        flags=re.IGNORECASE,
    )
    _HOUSE_ONLY_PATTERN = re.compile(
        rf"(?P<address>{_HOUSE_STREET})",
        flags=re.IGNORECASE,
    )
    _HOUSE_CITY_PATTERN = re.compile(
        rf"(?P<address>{_HOUSE_STREET}{_SEP}{_CITY})",
        flags=re.IGNORECASE,
    )
    _HOUSE_DISTRICT_PATTERN = re.compile(
        rf"(?P<address>{_HOUSE_STREET}{_SEP}{_DISTRICT_ANY})",
        flags=re.IGNORECASE,
    )
    _NO_CITY_PATTERN = re.compile(
        rf"(?P<address>{_HOUSE_STREET}{_SEP}{_WARD}{_SEP}{_DISTRICT_ANY})",
        flags=re.IGNORECASE,
    )
    _BUILDING_PATTERN = re.compile(
        rf"(?P<address>{_BUILDING}{_HOUSE_STREET}{_SEP}{_DISTRICT_ANY})",
        flags=re.IGNORECASE,
    )
    _DORM_PATTERN = re.compile(
        rf"(?P<address>(?:{_HOUSE_BLOCK}\s*,\s*)?(?:{_ROOM}\s*,\s*)?"
        rf"(?:ky{_INLINE_WS}tuc{_INLINE_WS}xa(?:{_INLINE_WS}[a-z0-9]+){{0,3}}\s*,\s*)?"
        rf"{_NEIGHBORHOOD}{_SEP}{_WARD_ANY}{_SEP}{_DISTRICT_ANY})",
        flags=re.IGNORECASE,
    )
    _HEURISTIC_KEYWORDS = (
        "so",
        "ngo",
        "duong",
        "phuong",
        "quan",
        "tp",
        "ha noi",
        "ho chi minh",
        "ngach",
        "hem",
        "pho",
        "xa",
        "huyen",
        "da nang",
    )
    _STRONG_ADDRESS_CUES = (
        "so",
        "ngo",
        "ngach",
        "hem",
        "duong",
        "pho",
    )
    _CONTEXT_CUES = (
        "dia chi",
        "nha toi",
        "o tai",
    )
    _BAD_SPAN_CUES = ("email", "@", "dev")
    _LOCATION_TERMS = ("duong", "pho", "ngo", "quan")
    _HEURISTIC_BOUNDARY = re.compile(r"[\r\n]|[.!?;](?:\s|$)")

    def scan(self, text: str) -> List[Entity]:
        raw_text = str(text or "")
        if not raw_text:
            return []

        folded_text, mapping = fold_text_with_mapping(raw_text)
        entities: list[Entity] = []
        seen_spans: set[tuple[int, int]] = set()

        for pattern, score, variant in (
            (self._FULL_PATTERN, 0.90, "full"),
            (self._DORM_PATTERN, 0.90, "dorm"),
            (self._BUILDING_PATTERN, 0.90, "building"),
            (self._SHORT_PATTERN, 0.90, "short"),
            (self._HOUSE_CITY_PATTERN, 0.90, "house_city"),
            (self._HOUSE_DISTRICT_PATTERN, 0.90, "house_district"),
            (self._NO_CITY_PATTERN, 0.90, "no_city"),
            (self._HOUSE_ONLY_PATTERN, 0.90, "house_only"),
        ):
            for match in pattern.finditer(folded_text):
                original_start, original_end = original_span_from_folded(
                    mapping=mapping,
                    folded_start=match.start("address"),
                    folded_end=match.end("address"),
                    original_length=len(raw_text),
                )
                if original_end <= original_start:
                    continue

                span = (original_start, original_end)
                if span in seen_spans:
                    continue
                if any(
                    span[0] >= seen_start and span[1] <= seen_end
                    for seen_start, seen_end in seen_spans
                ):
                    continue

                fragment = raw_text[original_start:original_end]
                if not self._is_valid_address_fragment(fragment):
                    continue

                self._append_entity(
                    entities=entities,
                    seen_spans=seen_spans,
                    start=original_start,
                    end=original_end,
                    raw_text=raw_text,
                    score=score,
                    variant=variant,
                )

        if not entities:
            heuristic_span = self._find_heuristic_span(
                raw_text=raw_text,
                folded_text=folded_text,
                mapping=mapping,
            )
            if heuristic_span is not None:
                self._append_entity(
                    entities=entities,
                    seen_spans=seen_spans,
                    start=heuristic_span[0],
                    end=heuristic_span[1],
                    raw_text=raw_text,
                    score=0.90,
                    variant="heuristic",
                )

        return entities

    def _append_entity(
        self,
        *,
        entities: list[Entity],
        seen_spans: set[tuple[int, int]],
        start: int,
        end: int,
        raw_text: str,
        score: float,
        variant: str,
    ) -> None:
        if end <= start:
            return

        span = (start, end)
        if span in seen_spans:
            return
        if any(start >= seen_start and end <= seen_end for seen_start, seen_end in seen_spans):
            return

        fragment = raw_text[start:end].strip(" ,:")
        if not self._is_valid_address_fragment(fragment):
            return

        leading_trim = len(raw_text[start:end]) - len(raw_text[start:end].lstrip(" ,:"))
        trailing_trim = len(raw_text[start:end]) - len(raw_text[start:end].rstrip(" ,:"))
        start += leading_trim
        end -= trailing_trim
        fragment = raw_text[start:end]
        if not self._is_valid_address_fragment(fragment):
            return

        seen_spans.add((start, end))
        entities.append(
            Entity(
                type="ADDRESS",
                start=start,
                end=end,
                score=score,
                source="vn_address",
                text=fragment,
                metadata={"format": variant},
            )
        )

    def _find_heuristic_span(
        self,
        *,
        raw_text: str,
        folded_text: str,
        mapping: list[int],
    ) -> tuple[int, int] | None:
        if not self._should_accept_heuristic(raw_text=raw_text, folded_text=folded_text):
            return None

        hits: list[tuple[int, str]] = []
        seen_keywords: set[str] = set()
        for keyword in self._HEURISTIC_KEYWORDS:
            idx = folded_text.find(keyword)
            if idx < 0:
                continue
            seen_keywords.add(keyword)
            hits.append((idx, keyword))

        if len(seen_keywords) < 2 or not hits:
            return None

        start_folded = min(idx for idx, _ in hits)
        boundary_match = self._HEURISTIC_BOUNDARY.search(raw_text, mapping[start_folded])
        end_original = boundary_match.start() if boundary_match else len(raw_text)
        if end_original <= mapping[start_folded]:
            return None

        start_original = mapping[start_folded]
        return (start_original, end_original)

    def _is_valid_address_fragment(self, fragment: str) -> bool:
        text = str(fragment or "").strip()
        if not text:
            return False

        # Keep the detector narrow: prose and multi-line snippets were the main
        # source of false positives in email-like bodies.
        if "\n" in text or "\r" in text:
            return False

        if re.fullmatch(r"\d+", text):
            return False

        folded_text = self._fold_text(text)
        if any(bad_word in folded_text for bad_word in self._BAD_SPAN_CUES):
            return False
        if "@" in text:
            return False
        if any(word in folded_text for word in self._BAD_SPAN_CUES):
            if not any(term in folded_text for term in self._LOCATION_TERMS):
                return False

        return self._has_house_number_signal(text)

    def _fold_text(self, text: str) -> str:
        raw = str(text or "").lower().replace("\u0111", "d")
        normalized = unicodedata.normalize("NFKD", raw)
        no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", no_marks).strip()

    def _has_strong_cue(self, folded_text: str) -> bool:
        return any(
            re.search(rf"(?<![a-z0-9]){re.escape(cue)}(?![a-z0-9])", folded_text)
            for cue in self._STRONG_ADDRESS_CUES
        )

    def _has_context_cue(self, folded_text: str) -> bool:
        return any(cue in folded_text for cue in self._CONTEXT_CUES)

    def _has_house_number_signal(self, text: str) -> bool:
        folded_text = self._fold_text(text)
        if re.search(self._HOUSE_STREET, folded_text, flags=re.IGNORECASE):
            return True
        if re.search(
            rf"{self._BUILDING}{self._HOUSE_STREET}",
            folded_text,
            flags=re.IGNORECASE,
        ):
            return True
        return False

    def _should_accept_heuristic(self, *, raw_text: str, folded_text: str) -> bool:
        if not self._has_house_number_signal(raw_text):
            return False

        if self._has_strong_cue(folded_text):
            return True

        return self._has_context_cue(folded_text)
