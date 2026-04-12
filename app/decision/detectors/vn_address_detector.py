from __future__ import annotations

import re
from typing import List

from app.decision.detectors.folded_text import (
    fold_text_with_mapping,
    original_span_from_folded,
)
from app.decision.detectors.local_regex_detector import Entity


class VietnameseAddressDetector:
    _HOUSE_NUMBER = r"\d{1,5}[a-z]?(?:/\d{1,4}[a-z]?)?"
    _HOUSE_STREET = (
        rf"{_HOUSE_NUMBER}(?:\s*,\s*|\s+)[a-z0-9]+(?:\s+[a-z0-9]+){{1,6}}"
    )
    _WARD = (
        r"(?:phuong|p\.?|xa|x\.?|thi tran|tt\.?)\s*[a-z0-9]+(?:\s+[a-z0-9]+){0,3}"
    )
    _DISTRICT = r"(?:(?:quan|q\.?)\s*\d{1,2}|(?:huyen|h\.?|thi xa|tx\.?)\s*[a-z0-9]+(?:\s+[a-z0-9]+){0,3})"
    _DISTRICT_PLAIN = r"(?:binh thanh|thu duc|go vap|tan binh|tan phu|phu nhuan|binh tan)"
    _DISTRICT_ANY = rf"(?:{_DISTRICT}|{_DISTRICT_PLAIN})"
    _CITY = (
        r"(?:tp\.?\s*[a-z0-9.]+|thanh pho\s+[a-z0-9]+(?:\s+[a-z0-9]+){0,3}|tinh\s+[a-z0-9]+(?:\s+[a-z0-9]+){0,3})"
    )
    _BUILDING = (
        r"(?:(?:tang\s*\d+[a-z]?\s*,\s*(?:toa\s+nha\s+[a-z0-9]+(?:\s+[a-z0-9]+){0,4}\s*,\s*)?)|(?:toa\s+nha\s+[a-z0-9]+(?:\s+[a-z0-9]+){0,4}\s*,\s*))"
    )
    _ROOM = r"phong\s*[a-z0-9]+(?:/[a-z0-9]+)?"
    _HOUSE_BLOCK = r"nha\s*[a-z0-9]+(?:\s+[a-z0-9]+){0,2}"
    _NEIGHBORHOOD = r"khu\s+pho\s*[a-z0-9]+(?:\s+[a-z0-9]+){0,2}"
    _WARD_PLAIN = r"(?:linh trung|linh tay|linh xuan|ben nghe|ben thanh)"
    _WARD_ANY = rf"(?:{_WARD}|{_WARD_PLAIN})"
    _FULL_PATTERN = re.compile(
        rf"(?P<address>{_HOUSE_STREET}(?:\s*,\s*|\s+){_WARD}(?:\s*,\s*|\s+){_DISTRICT}(?:\s*,\s*|\s+){_CITY})",
        flags=re.IGNORECASE,
    )
    _SHORT_PATTERN = re.compile(
        rf"(?P<address>{_HOUSE_STREET}(?:\s*,\s*|\s+){_DISTRICT}(?:\s*,\s*|\s+){_CITY})",
        flags=re.IGNORECASE,
    )
    _NO_CITY_PATTERN = re.compile(
        rf"(?P<address>{_HOUSE_STREET}(?:\s*,\s*|\s+){_WARD}(?:\s*,\s*|\s+){_DISTRICT_ANY})",
        flags=re.IGNORECASE,
    )
    _BUILDING_PATTERN = re.compile(
        rf"(?P<address>{_BUILDING}{_HOUSE_STREET}(?:\s*,\s*|\s+){_DISTRICT_ANY})",
        flags=re.IGNORECASE,
    )
    _DORM_PATTERN = re.compile(
        rf"(?P<address>(?:{_HOUSE_BLOCK}\s*,\s*)?(?:{_ROOM}\s*,\s*)?(?:ky\s+tuc\s+xa(?:\s+[a-z0-9]+){{0,3}}\s*,\s*)?{_NEIGHBORHOOD}(?:\s*,\s*|\s+){_WARD_ANY}(?:\s*,\s*|\s+){_DISTRICT_ANY})",
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
                seen_spans.add(span)

                fragment = raw_text[original_start:original_end]
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
