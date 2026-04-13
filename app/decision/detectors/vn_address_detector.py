from __future__ import annotations

import re
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
    _HOUSE_STREET = (
        rf"{_HOUSE_NUMBER}{_SEP}[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{1,5}}"
    )
    _WARD_MARKER = (
        rf"(?:phuong|xa|thi{_INLINE_WS}tran|p\b\.?|x\b\.?|tt\b\.?)"
    )
    _WARD = (
        rf"{_WARD_MARKER}{_INLINE_WS}[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{0,3}}"
    )
    _DISTRICT = (
        rf"(?:(?:quan{_INLINE_WS}|q\b\.?{_OPT_INLINE_WS})\d{{1,2}}|"
        rf"(?:huyen|thi{_INLINE_WS}xa|h\b\.?|tx\b\.?){_INLINE_WS}"
        rf"[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{0,3}})"
    )
    _DISTRICT_PLAIN = r"(?:binh thanh|thu duc|go vap|tan binh|tan phu|phu nhuan|binh tan)"
    _DISTRICT_ANY = rf"(?:{_DISTRICT}|{_DISTRICT_PLAIN})"
    _CITY = (
        rf"(?:tp\.?{_OPT_INLINE_WS}[a-z0-9.]+|thanh{_INLINE_WS}pho{_INLINE_WS}"
        rf"[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{0,3}}|"
        rf"tinh{_INLINE_WS}[a-z0-9]+(?:{_INLINE_WS}[a-z0-9]+){{0,3}})"
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

    def scan(self, text: str) -> List[Entity]:
        raw_text = str(text or "")
        if not raw_text:
            return []

        folded_text, mapping = fold_text_with_mapping(raw_text)
        entities: list[Entity] = []
        seen_spans: set[tuple[int, int]] = set()

        for pattern, score, variant in (
            (self._FULL_PATTERN, 0.91, "full"),
            (self._DORM_PATTERN, 0.90, "dorm"),
            (self._BUILDING_PATTERN, 0.89, "building"),
            (self._SHORT_PATTERN, 0.86, "short"),
            (self._NO_CITY_PATTERN, 0.86, "no_city"),
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

                seen_spans.add(span)
                entities.append(
                    Entity(
                        type="ADDRESS",
                        start=original_start,
                        end=original_end,
                        score=score,
                        source="vn_address",
                        text=fragment,
                        metadata={"format": variant},
                    )
                )

        return entities

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

        return True
