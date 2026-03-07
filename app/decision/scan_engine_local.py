# app/decision/scan_engine_local.py
from __future__ import annotations

import time
from typing import Any, Optional
from uuid import UUID

from sqlmodel import Session

from app.decision.context_scorer import ContextScorer
from app.decision.context_term_runtime import load_context_runtime_overrides
from app.decision.decision_resolver import DecisionResolver
from app.decision.detectors.local_regex_detector import LocalRegexDetector
from app.decision.detectors.presidio_detector import PresidioDetector
from app.decision.detectors.security_injection_detector import SecurityInjectionDetector
from app.decision.detectors.spoken_number_detector import SpokenNumberDetector
from app.decision.entity_merger import EntityMerger, MergeConfig
from app.decision.entity_type_normalizer import EntityTypeNormalizer
from app.decision.rule_layering import compact_matches
from app.rag.rag_verifier import RagVerifier
from app.rule.engine import RuleEngine


class ScanEngineLocal:
    def __init__(self, *, context_yaml_path: str):
        self.local = LocalRegexDetector()
        self.presidio = PresidioDetector()
        self.security = SecurityInjectionDetector()
        self.spoken = SpokenNumberDetector()

        self.context = ContextScorer(context_yaml_path)
        self.rule_engine = RuleEngine()
        self.resolver = DecisionResolver()
        self.rag = RagVerifier()

        self.type_norm = EntityTypeNormalizer()
        self.merger = EntityMerger(
            MergeConfig(
                overlap_threshold=0.80,
                prefer_source_order=("local_regex", "spoken_norm", "presidio"),
            )
        )

    def _should_call_rag(
        self,
        *,
        sec_decision: str,
        persona: Optional[str],
        context_keywords: list[str],
        entities: list[Any],
        spoken_entities: list[Any],
    ) -> bool:
        if sec_decision == "BLOCK":
            return False

        if sec_decision == "REVIEW":
            return True

        if spoken_entities:
            return True

        dev_kws = {"api key", "apikey", "token", "secret", "bearer", ".env"}
        if persona == "dev" and any(k in dev_kws for k in context_keywords):
            has_secret = any(getattr(e, "type", "") == "API_SECRET" for e in entities)
            if not has_secret:
                return True

        return False

    async def scan(
        self, *, session: Session, text: str, company_id: Optional[UUID]
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        overrides = load_context_runtime_overrides(
            session=session,
            company_id=company_id,
        )

        # 1) entities
        regex_entities = self.local.scan(
            text,
            context_hints_by_entity=overrides.regex_hints,
        )
        spoken_entities = self.spoken.scan(text)
        presidio_entities = self.presidio.scan(text)

        # 2) normalize
        for e in regex_entities + spoken_entities + presidio_entities:
            e.type = self.type_norm.normalize(getattr(e, "type", ""))

        # 3) merge
        entities = self.merger.merge(
            regex_entities + spoken_entities + presidio_entities
        )

        # 4) context
        ctx = self.context.score(
            text,
            persona_keywords_override=overrides.persona_keywords,
        )
        signals = self.context.to_signals_dict(ctx)

        # 5) security
        sec = self.security.scan(text)
        signals["security"] = {
            "decision": sec.decision,
            "score": sec.score,
            "reason": sec.reason,
            "prompt_injection": sec.prompt_injection,
            "prompt_injection_block": sec.decision == "BLOCK",
            "prompt_injection_suspected": sec.decision in ("REVIEW", "BLOCK"),
        }

        # 6) gating
        should_rag = self._should_call_rag(
            sec_decision=str(sec.decision),
            persona=signals.get("persona"),
            context_keywords=list(signals.get("context_keywords") or []),
            entities=entities,
            spoken_entities=spoken_entities,
        )

        # 7) RAG only when needed
        if should_rag:
            rag_out = await self.rag.decide(
                session=session,
                user_text=text,
                company_id=company_id,
                message_id=None,
            )
            signals["rag"] = {
                "decision": rag_out.decision,  # ALLOW/MASK/BLOCK
                "confidence": rag_out.confidence,
                "rule_keys": rag_out.rule_keys,
                "rationale": rag_out.rationale,
            }
        else:
            signals.pop("rag", None)

        # 8) rules
        matches = self.rule_engine.evaluate(
            session=session,
            company_id=company_id,
            entities=entities,
            signals=signals,
        )
        decision = self.resolver.resolve(matches)

        # ✅ compact log (fix "mask 2 lần" trong matched_rules)
        matches = compact_matches(
            matches, final_action=str(decision.final_action).lower()
        )

        latency_ms = int((time.perf_counter() - t0) * 1000)
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
            "ambiguous": should_rag,
        }
