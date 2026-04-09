from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata
from typing import Any, Optional

import yaml


@dataclass(slots=True)
class ContextSignals:
    persona: Optional[str]
    keyword_hits: list[str]
    risk_boost: float


class ContextScorer:
    """
    Build context signals only (no entity span creation).
    """

    def __init__(self, yaml_path: str | Path):
        self.yaml_path = Path(yaml_path)
        data = yaml.safe_load(self.yaml_path.read_text(encoding="utf-8")) or {}

        personas = data.get("personas") or {}
        self.persona_keywords: dict[str, list[str]] = {
            persona: [kw.lower() for kw in (cfg.get("keywords") or [])]
            for persona, cfg in personas.items()
        }

    def _fold_text(self, text: str) -> str:
        raw = str(text or "").lower().replace("\u0111", "d")
        normalized = unicodedata.normalize("NFKD", raw)
        no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", no_marks).strip()

    def _keyword_in_text(self, *, text_raw: str, text_fold: str, keyword: str) -> bool:
        kw_raw = str(keyword or "").lower().strip()
        if not kw_raw:
            return False
        if kw_raw in text_raw:
            return True
        return self._fold_text(kw_raw) in text_fold

    def score(
        self,
        text: str,
        *,
        persona_keywords_override: dict[str, list[str]] | None = None,
    ) -> ContextSignals:
        text_raw = (text or "").lower()
        text_fold = self._fold_text(text)

        active_keywords: dict[str, list[str]] = {
            k: list(v) for k, v in self.persona_keywords.items()
        }
        if persona_keywords_override:
            for persona, kws in persona_keywords_override.items():
                normalized = [str(kw).lower() for kw in (kws or []) if str(kw).strip()]
                if normalized:
                    merged = active_keywords.get(persona, []) + normalized
                    deduped: list[str] = []
                    seen: set[str] = set()
                    for keyword in merged:
                        if keyword in seen:
                            continue
                        seen.add(keyword)
                        deduped.append(keyword)
                    active_keywords[persona] = deduped

        best_persona: Optional[str] = None
        best_hits: list[str] = []

        for persona, kws in active_keywords.items():
            hits = [
                kw
                for kw in kws
                if self._keyword_in_text(text_raw=text_raw, text_fold=text_fold, keyword=kw)
            ]
            if len(hits) > len(best_hits):
                best_persona = persona
                best_hits = hits

        risk_boost = 0.0
        if best_persona == "dev" and best_hits:
            risk_boost = 0.15
        elif best_persona == "office" and best_hits:
            risk_boost = 0.10

        return ContextSignals(
            persona=best_persona,
            keyword_hits=best_hits[:10],
            risk_boost=risk_boost,
        )

    def to_signals_dict(self, ctx: ContextSignals) -> dict[str, Any]:
        return {
            "persona": ctx.persona,
            "context_keywords": ctx.keyword_hits,
            "risk_boost": ctx.risk_boost,
        }
