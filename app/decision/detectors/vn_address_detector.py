from __future__ import annotations

import re
from typing import List

from app.decision.detectors.folded_text import (
    fold_text_with_mapping,
    original_span_from_folded,
)
from app.decision.detectors.local_regex_detector import Entity


class VietnameseAddressDetector:
    _HOUSE_STREET = (
        r"\d{1,5}(?:/\d{1,4})?(?:\s*,\s*|\s+)[a-z0-9]+(?:\s+[a-z0-9]+){1,6}"
    )
    _WARD = (
        r"(?:phuong|p\.?|xa|x\.?|thi tran|tt\.?)\s*[a-z0-9]+(?:\s+[a-z0-9]+){0,3}"
    )
    _DISTRICT = (
        r"(?:quan|q\.?|huyen|h\.?|thi xa|tx\.?)\s*[a-z0-9]+(?:\s+[a-z0-9]+){0,3}"
    )
    _CITY = (
        r"(?:tp\.?\s*[a-z0-9.]+|thanh pho\s+[a-z0-9]+(?:\s+[a-z0-9]+){0,3}|tinh\s+[a-z0-9]+(?:\s+[a-z0-9]+){0,3})"
    )
    _FULL_PATTERN = re.compile(
        rf"(?P<address>{_HOUSE_STREET}(?:\s*,\s*|\s+){_WARD}(?:\s*,\s*|\s+){_DISTRICT}(?:\s*,\s*|\s+){_CITY})",
        flags=re.IGNORECASE,
    )
    _SHORT_PATTERN = re.compile(
        rf"(?P<address>{_HOUSE_STREET}(?:\s*,\s*|\s+){_DISTRICT}(?:\s*,\s*|\s+){_CITY})",
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
            (self._SHORT_PATTERN, 0.86, "short"),
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
