from __future__ import annotations

import time
from typing import Any, Optional
from uuid import UUID

from sqlmodel import Session

from app.decision.context_scorer import ContextScorer
from app.decision.detectors.local_regex_detector import LocalRegexDetector
from app.decision.detectors.presidio_detector import PresidioDetector
from app.decision.decision_resolver import DecisionResolver
from app.rule.engine import RuleEngine


class ScanEngineLocal:
    def __init__(self, *, context_yaml_path: str):
        self.local = LocalRegexDetector()
        self.presidio = PresidioDetector()  # ✅ THÊM DÒNG NÀY
        self.context = ContextScorer(context_yaml_path)
        self.rule_engine = RuleEngine()
        self.resolver = DecisionResolver()

    def scan(
        self, *, session: Session, text: str, company_id: Optional[UUID]
    ) -> dict[str, Any]:
        t0 = time.perf_counter()

        regex_entities = self.local.scan(text)
        presidio_entities = self.presidio.scan(text)

        # MVP: cứ cộng list, merger nâng cao làm sau
        entities = regex_entities + presidio_entities

        ctx = self.context.score(text)
        signals = self.context.to_signals_dict(ctx)

        matches = self.rule_engine.evaluate(
            session=session,
            company_id=company_id,
            entities=entities,
            signals=signals,
        )

        decision = self.resolver.resolve(matches)

        latency_ms = int((time.perf_counter() - t0) * 1000)

        max_entity = max(
            [float(getattr(e, "score", 0.0)) for e in entities], default=0.0
        )
        risk_score = min(1.0, max_entity + float(signals.get("risk_boost", 0.0) or 0.0))

        ambiguous = False

        return {
            "entities": entities,
            "signals": signals,
            "matches": matches,
            "final_action": decision.final_action,
            "latency_ms": latency_ms,
            "risk_score": risk_score,
            "ambiguous": ambiguous,
        }