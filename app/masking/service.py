# app/masking/service.py
from __future__ import annotations

from dataclasses import dataclass
import re

from app.decision.entity_priority import entity_type_priority, source_priority

MASKABLE_TYPES = {
    "PHONE",
    "EMAIL",
    "TAX_ID",
    "CREDIT_CARD",
    "CCCD",
    "ADDRESS",
    "API_SECRET",
}
_CODE_LIKE_TERM_RE = re.compile(r"[A-Za-z0-9]{2,}(?:[-_][A-Za-z0-9]{1,}){1,}")
_MASK_PLACEHOLDER_RE = re.compile(r"\[[A-Z0-9_]+\]")


@dataclass(slots=True)
class Span:
    start: int
    end: int
    type: str
    score: float
    source: str


class MaskService:
    def _replace_exact_terms_in_plain_segment(
        self,
        *,
        text: str,
        ordered_terms: list[str],
    ) -> str:
        out = text
        for term in ordered_terms:
            pattern = re.compile(re.escape(term), flags=re.IGNORECASE)
            out = pattern.sub("[INTERNAL_CODE]", out)
        return out

    def _mask_exact_terms(self, text: str, exact_terms: list[str]) -> str:
        ordered = sorted(
            {
                str(term or "").strip()
                for term in exact_terms
                if str(term or "").strip()
            },
            key=len,
            reverse=True,
        )
        if not ordered:
            return text

        parts: list[str] = []
        cursor = 0
        for match in _MASK_PLACEHOLDER_RE.finditer(text):
            start, end = match.span()
            if start > cursor:
                parts.append(
                    self._replace_exact_terms_in_plain_segment(
                        text=text[cursor:start],
                        ordered_terms=ordered,
                    )
                )
            parts.append(match.group(0))
            cursor = end

        if cursor < len(text):
            parts.append(
                self._replace_exact_terms_in_plain_segment(
                    text=text[cursor:],
                    ordered_terms=ordered,
                )
            )

        return "".join(parts)

    def mask(
        self,
        text: str,
        entities: list,
        *,
        extra_terms: list[str] | None = None,
        force_terms: list[str] | None = None,
    ) -> str:
        if not text:
            return text

        raw_extra_terms = list(extra_terms or [])
        raw_force_terms = [
            str(term or "").strip()
            for term in list(force_terms or [])
            if str(term or "").strip()
        ]
        code_like_terms = [
            term
            for term in raw_extra_terms
            if _CODE_LIKE_TERM_RE.search(str(term or "").strip()) is not None
        ]

        spans: list[Span] = []
        n = len(text)

        for entity in entities:
            entity_type = getattr(entity, "type", None)
            if entity_type not in MASKABLE_TYPES:
                continue

            start = int(getattr(entity, "start", 0))
            end = int(getattr(entity, "end", 0))
            start = max(0, min(start, n))
            end = max(0, min(end, n))
            if end <= start:
                continue

            spans.append(
                Span(
                    start=start,
                    end=end,
                    type=str(entity_type),
                    score=float(getattr(entity, "score", 0.0) or 0.0),
                    source=str(getattr(entity, "source", "")),
                )
            )

        if not spans:
            if not code_like_terms and not raw_force_terms:
                return text
            out = text
            if code_like_terms:
                out = self._mask_exact_terms(out, code_like_terms)
            if raw_force_terms:
                out = self._mask_exact_terms(out, raw_force_terms)
            return out

        spans.sort(key=lambda span: (span.start, -(span.end - span.start), -span.score))

        chosen: list[Span] = []
        for span in spans:
            if not chosen:
                chosen.append(span)
                continue

            last = chosen[-1]
            if span.start >= last.end:
                chosen.append(span)
                continue

            if self._span_precedence_key(span) > self._span_precedence_key(last):
                chosen[-1] = span

        out = text
        for span in sorted(chosen, key=lambda item: item.start, reverse=True):
            label = f"[{span.type}]"
            out = out[: span.start] + label + out[span.end :]

        if code_like_terms:
            out = self._mask_exact_terms(out, code_like_terms)
        if raw_force_terms:
            out = self._mask_exact_terms(out, raw_force_terms)
        return out

    def _span_precedence_key(self, span: Span) -> tuple[int, int, float, int]:
        return (
            entity_type_priority(span.type),
            max(0, int(span.end) - int(span.start)),
            float(span.score),
            source_priority(span.source),
        )
