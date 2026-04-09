from __future__ import annotations

import re
from typing import List

from app.decision.detectors.folded_text import (
    fold_text_with_mapping,
    original_span_from_folded,
)
from app.decision.detectors.local_regex_detector import Entity


class ObfuscatedEmailDetector:
    _AT_PATTERN = re.compile(
        r"(?<![a-z0-9])(?:@|a\s+cong|acong|at)(?![a-z0-9])",
        flags=re.IGNORECASE,
    )
    _LEFT_PATTERN = re.compile(
        r"([a-z0-9]+(?:(?:\s*(?:[._%+\-])\s*|\s+(?:dot|cham|underscore|gach duoi|dash|gach ngang|hyphen|plus)\s+|\s+)[a-z0-9]+){0,5})\s*$",
        flags=re.IGNORECASE,
    )
    _RIGHT_PATTERN = re.compile(
        r"^\s*([a-z0-9]+(?:-[a-z0-9]+)*(?:\s*(?:[.]|dot|cham)\s*[a-z0-9]+(?:-[a-z0-9]+)*){1,3})",
        flags=re.IGNORECASE,
    )
    _TOKEN_PATTERN = re.compile(r"[a-z0-9]+", flags=re.IGNORECASE)
    _LEADING_STOPWORDS = {
        "la",
        "cua",
        "toi",
        "minh",
        "mail",
        "email",
        "gmail",
        "dia",
        "chi",
    }
    _KNOWN_PROVIDERS = {
        "gmail",
        "yahoo",
        "hotmail",
        "outlook",
        "icloud",
        "protonmail",
    }

    def scan(self, text: str) -> List[Entity]:
        raw_text = str(text or "")
        if not raw_text:
            return []

        folded_text, mapping = fold_text_with_mapping(raw_text)
        entities: list[Entity] = []
        seen_spans: set[tuple[int, int]] = set()

        for at_match in self._AT_PATTERN.finditer(folded_text):
            left_candidate = self._extract_left_local_part(
                folded_text=folded_text,
                at_start=at_match.start(),
            )
            if left_candidate is None:
                continue

            right_match = self._RIGHT_PATTERN.match(folded_text[at_match.end() :])
            if right_match is None:
                continue

            local_start, local_end, normalized_local = left_candidate
            normalized_domain = self._normalize_domain(right_match.group(1))
            if "." not in normalized_domain:
                continue

            domain_labels = [part for part in normalized_domain.split(".") if part]
            if len(domain_labels) < 2:
                continue
            if not domain_labels[-1].isalpha() or len(domain_labels[-1]) < 2:
                continue

            folded_start = local_start
            folded_end = at_match.end() + right_match.end()
            original_start, original_end = original_span_from_folded(
                mapping=mapping,
                folded_start=folded_start,
                folded_end=folded_end,
                original_length=len(raw_text),
            )
            if original_end <= original_start:
                continue

            span = (original_start, original_end)
            if span in seen_spans:
                continue
            seen_spans.add(span)

            provider = domain_labels[0]
            score = 0.91 if provider in self._KNOWN_PROVIDERS else 0.86
            entities.append(
                Entity(
                    type="EMAIL",
                    start=original_start,
                    end=original_end,
                    score=score,
                    source="spoken_email",
                    text=raw_text[original_start:original_end],
                    metadata={
                        "normalized": f"{normalized_local}@{normalized_domain}",
                        "obfuscated": True,
                    },
                )
            )

        return entities

    def _extract_left_local_part(
        self,
        *,
        folded_text: str,
        at_start: int,
    ) -> tuple[int, int, str] | None:
        left_window_start = max(0, int(at_start) - 96)
        left_window = folded_text[left_window_start:at_start]
        left_match = self._LEFT_PATTERN.search(left_window)
        if left_match is None:
            return None

        local_text = left_match.group(1)
        token_matches = list(self._TOKEN_PATTERN.finditer(local_text))
        if not token_matches:
            return None

        drop_count = 0
        for token_match in token_matches:
            if token_match.group(0).lower() not in self._LEADING_STOPWORDS:
                break
            drop_count += 1

        if drop_count >= len(token_matches):
            return None

        local_start_in_match = token_matches[drop_count].start()
        trimmed_local = local_text[local_start_in_match:].strip()
        normalized_local = self._normalize_local(trimmed_local)
        local_tokens = [part for part in re.split(r"[._%+\-]+", normalized_local) if part]
        if not normalized_local or not local_tokens:
            return None
        if len(local_tokens) > 6:
            return None

        folded_local_start = left_window_start + left_match.start(1) + local_start_in_match
        folded_local_end = left_window_start + left_match.end(1)
        return (folded_local_start, folded_local_end, normalized_local)

    def _normalize_local(self, value: str) -> str:
        normalized = str(value or "").lower()
        replacements = (
            (r"\s+(?:dot|cham)\s+", "."),
            (r"\s+underscore\s+|\s+gach duoi\s+", "_"),
            (r"\s+(?:dash|gach ngang|hyphen)\s+", "-"),
            (r"\s+plus\s+", "+"),
        )
        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized)

        normalized = re.sub(r"\s+", "", normalized)
        normalized = re.sub(r"\.+", ".", normalized)
        normalized = normalized.strip(".")
        return normalized

    def _normalize_domain(self, value: str) -> str:
        normalized = str(value or "").lower()
        normalized = re.sub(r"\s*(?:dot|cham)\s*", ".", normalized)
        normalized = re.sub(r"\s+", "", normalized)
        normalized = re.sub(r"\.+", ".", normalized)
        return normalized.strip(".")
