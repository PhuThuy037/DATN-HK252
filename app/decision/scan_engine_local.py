from __future__ import annotations

import time
from typing import Any, Optional
from uuid import UUID

from sqlmodel import Session

from app.decision.context_scorer import ContextScorer
from app.decision.detectors.local_regex_detector import LocalRegexDetector
from app.decision.detectors.presidio_detector import PresidioDetector
from app.decision.detectors.security_injection_detector import SecurityInjectionDetector
from app.decision.decision_resolver import DecisionResolver
from app.rule.engine import RuleEngine

from app.decision.entity_type_normalizer import EntityTypeNormalizer
from app.decision.entity_merger import EntityMerger, MergeConfig


class ScanEngineLocal:
    def __init__(self, *, context_yaml_path: str):
        self.local = LocalRegexDetector()
        self.presidio = PresidioDetector()
        self.security = SecurityInjectionDetector()

        self.context = ContextScorer(context_yaml_path)
        self.rule_engine = RuleEngine()
        self.resolver = DecisionResolver()

        self.type_norm = EntityTypeNormalizer()
        self.merger = EntityMerger(
            MergeConfig(
                overlap_threshold=0.80,
                prefer_source_order=("local_regex", "presidio"),
            )
        )

    async def scan(
        self, *, session: Session, text: str, company_id: Optional[UUID]
    ) -> dict[str, Any]:
        t0 = time.perf_counter()

        # 1) collect entities
        regex_entities = self.local.scan(text)
        presidio_entities = self.presidio.scan(text)

        # 2) normalize entity types (để RuleEngine match ổn định)
        for e in regex_entities:
            e.type = self.type_norm.normalize(getattr(e, "type", ""))
        for e in presidio_entities:
            e.type = self.type_norm.normalize(getattr(e, "type", ""))

        # 3) merge entities
        entities = self.merger.merge(regex_entities + presidio_entities)

        # 4) context signals
        ctx = self.context.score(text)
        signals = self.context.to_signals_dict(ctx)

        # 5) security signals (KHÔNG phải entity)
        sec = self.security.scan(text)
        signals["security"] = {
            "decision": sec.decision,
            "score": sec.score,
            "reason": sec.reason,
            "prompt_injection": sec.prompt_injection,
            "prompt_injection_block": (sec.decision == "BLOCK"),
            "prompt_injection_suspected": (sec.decision in ("REVIEW", "BLOCK")),
        }

        # 6) rules + decision
        matches = self.rule_engine.evaluate(
            session=session,
            company_id=company_id,
            entities=entities,
            signals=signals,
        )
        decision = self.resolver.resolve(matches)

        latency_ms = int((time.perf_counter() - t0) * 1000)

        # risk_score MVP: max entity score + risk_boost
        max_entity = max(
            [float(getattr(e, "score", 0.0)) for e in entities], default=0.0
        )
        risk_score = min(1.0, max_entity + float(signals.get("risk_boost", 0.0) or 0.0))

        return {
            "entities": entities,
            "signals": signals,
            "matches": matches,
            "final_action": decision.final_action,
            "latency_ms": latency_ms,
            "risk_score": risk_score,
            "ambiguous": False,
        }