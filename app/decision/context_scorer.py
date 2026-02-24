from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass(slots=True)
class ContextSignals:
    persona: Optional[str]
    keyword_hits: list[str]
    risk_boost: float


class ContextScorer:
    """
    ContextScorer chỉ tạo SIGNALS, KHÔNG tạo span.
    - persona: "dev" | "office" | None
    - keyword_hits: keyword hit (top N)
    - risk_boost: cộng điểm rủi ro
    """

    def __init__(self, yaml_path: str | Path):
        self.yaml_path = Path(yaml_path)
        data = yaml.safe_load(self.yaml_path.read_text(encoding="utf-8")) or {}

        personas = data.get("personas") or {}
        self.persona_keywords: dict[str, list[str]] = {
            persona: [kw.lower() for kw in (cfg.get("keywords") or [])]
            for persona, cfg in personas.items()
        }

    def score(self, text: str) -> ContextSignals:
        t = (text or "").lower()

        best_persona: Optional[str] = None
        best_hits: list[str] = []

        for persona, kws in self.persona_keywords.items():
            hits = [kw for kw in kws if kw in t]
            if len(hits) > len(best_hits):
                best_persona = persona
                best_hits = hits

        # risk boost MVP (mày chỉnh sau)
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