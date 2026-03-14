# app/masking/service.py
from __future__ import annotations

from dataclasses import dataclass
import re

MASKABLE_TYPES = {"PHONE", "EMAIL", "TAX_ID", "CREDIT_CARD", "CCCD"}
_CODE_LIKE_TERM_RE = re.compile(r"[A-Za-z0-9]{2,}(?:[-_][A-Za-z0-9]{1,}){1,}")


@dataclass(slots=True)
class Span:
    start: int
    end: int
    type: str
    score: float
    source: str


class MaskService:
    def _mask_exact_terms(self, text: str, exact_terms: list[str]) -> str:
        out = text
        # Mask longer terms first to avoid partial replacement collisions.
        ordered = sorted(
            {
                str(term or "").strip()
                for term in exact_terms
                if str(term or "").strip()
            },
            key=len,
            reverse=True,
        )
        for term in ordered:
            pattern = re.compile(re.escape(term), flags=re.IGNORECASE)
            out = pattern.sub("[INTERNAL_CODE]", out)
        return out

    def mask(
        self,
        text: str,
        entities: list,
        *,
        extra_terms: list[str] | None = None,
    ) -> str:
        if not text:
            return text

        raw_extra_terms = list(extra_terms or [])
        code_like_terms = [
            term
            for term in raw_extra_terms
            if _CODE_LIKE_TERM_RE.search(str(term or "").strip()) is not None
        ]

        spans: list[Span] = []
        n = len(text)

        for e in entities:
            etype = getattr(e, "type", None)
            if etype not in MASKABLE_TYPES:
                continue

            start = int(getattr(e, "start", 0))
            end = int(getattr(e, "end", 0))

            # clamp
            start = max(0, min(start, n))
            end = max(0, min(end, n))
            if end <= start:
                continue

            spans.append(
                Span(
                    start=start,
                    end=end,
                    type=etype,
                    score=float(getattr(e, "score", 0.0)),
                    source=str(getattr(e, "source", "")),
                )
            )

        if not spans:
            if not code_like_terms:
                return text
            return self._mask_exact_terms(text, code_like_terms)

        # 1) sort theo start asc, rồi chọn span tốt nhất khi overlap
        spans.sort(key=lambda s: (s.start, -(s.end - s.start), -s.score))

        chosen: list[Span] = []
        for s in spans:
            if not chosen:
                chosen.append(s)
                continue

            last = chosen[-1]
            if s.start >= last.end:
                chosen.append(s)
                continue

            # overlap -> chọn cái "tốt hơn"
            # ưu tiên span dài hơn, score cao hơn, source local_regex > spoken_norm > presidio
            def src_rank(src: str) -> int:
                if src == "local_regex":
                    return 3
                if src == "spoken_norm":
                    return 2
                return 1

            last_len = last.end - last.start
            s_len = s.end - s.start

            better = False
            if s_len > last_len:
                better = True
            elif s_len == last_len and s.score > last.score:
                better = True
            elif (
                s_len == last_len
                and s.score == last.score
                and src_rank(s.source) > src_rank(last.source)
            ):
                better = True

            if better:
                chosen[-1] = s
            # else bỏ s

        # 2) replace từ phải qua trái
        out = text
        for s in sorted(chosen, key=lambda x: x.start, reverse=True):
            label = f"[{s.type}]"
            out = out[: s.start] + label + out[s.end :]

        if not code_like_terms:
            return out
        return self._mask_exact_terms(out, code_like_terms)
