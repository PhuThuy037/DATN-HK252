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

    def _is_strong_spoken_signal(self, spoken_entities: list[Any]) -> bool:
        if not spoken_entities:
            return False
        for e in spoken_entities:
            etype = str(getattr(e, "type", "") or "")
            score = float(getattr(e, "score", 0.0) or 0.0)
            if etype not in {"PHONE", "CCCD", "TAX_ID"}:
                return False
            if score < 0.82:
                return False
        return True

    def _should_run_presidio(
        self,
        *,
        text: str,
        sec_decision: str,
        regex_entities: list[Any],
        spoken_entities: list[Any],
    ) -> bool:
        if regex_entities or spoken_entities:
            return False

        if sec_decision == "BLOCK":
            return False

        raw = text or ""
        lower = raw.lower()

        if "@" in raw or "http://" in lower or "https://" in lower:
            return True

        letters = [ch for ch in raw if ch.isalpha()]
        if not letters:
            return False
        ascii_letters = sum(1 for ch in letters if ord(ch) < 128)
        ascii_ratio = ascii_letters / float(len(letters))
        return ascii_ratio >= 0.85

    def _should_call_rag(
        self,
        *,
        sec_decision: str,
        sec_score: float,
        persona: Optional[str],
        context_keywords: list[str],
        entities: list[Any],
        spoken_entities: list[Any],
    ) -> bool:
        if sec_decision == "BLOCK":
            return False

        if sec_decision == "REVIEW":
            return True

        has_high_conf_api_secret = any(
            str(getattr(e, "type", "") or "") == "API_SECRET"
            and float(getattr(e, "score", 0.0) or 0.0) >= 0.90
            for e in entities
        )
        if has_high_conf_api_secret:
            # Keep RAG when persona is not clearly dev to reduce false negatives.
            return persona != "dev"

        if spoken_entities:
            return not self._is_strong_spoken_signal(spoken_entities)

        dev_kws = {"api key", "apikey", "token", "secret", "bearer", ".env", "authorization"}
        lowered_kws = {str(k or "").lower() for k in context_keywords}
        if persona == "dev" and (lowered_kws & dev_kws):
            has_secret = any(
                str(getattr(e, "type", "") or "") == "API_SECRET"
                and float(getattr(e, "score", 0.0) or 0.0) >= 0.85
                for e in entities
            )
            if has_secret:
                return False
            if float(sec_score) >= 0.25:
                return True

        return False

    async def scan(
        self, *, session: Session, text: str, company_id: Optional[UUID]
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        timing_ms_by_stage: dict[str, int] = {}

        ts = time.perf_counter()
        overrides = load_context_runtime_overrides(
            session=session,
            company_id=company_id,
        )
        timing_ms_by_stage["overrides"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        regex_entities = self.local.scan(
            text,
            context_hints_by_entity=overrides.regex_hints,
        )
        timing_ms_by_stage["detect_regex"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        spoken_entities = self.spoken.scan(text)
        timing_ms_by_stage["detect_spoken"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        sec = self.security.scan(text)
        timing_ms_by_stage["detect_security"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        if self._should_run_presidio(
            text=text,
            sec_decision=str(sec.decision),
            regex_entities=regex_entities,
            spoken_entities=spoken_entities,
        ):
            presidio_entities = self.presidio.scan(text)
        else:
            presidio_entities = []
        timing_ms_by_stage["detect_presidio"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        for e in regex_entities + spoken_entities + presidio_entities:
            e.type = self.type_norm.normalize(getattr(e, "type", ""))
        timing_ms_by_stage["normalize_entities"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        entities = self.merger.merge(
            regex_entities + spoken_entities + presidio_entities
        )
        timing_ms_by_stage["merge_entities"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        ctx = self.context.score(
            text,
            persona_keywords_override=overrides.persona_keywords,
        )
        signals = self.context.to_signals_dict(ctx)
        timing_ms_by_stage["context_score"] = int((time.perf_counter() - ts) * 1000)

        signals["security"] = {
            "decision": sec.decision,
            "score": sec.score,
            "reason": sec.reason,
            "prompt_injection": sec.prompt_injection,
            "prompt_injection_block": sec.decision == "BLOCK",
            "prompt_injection_suspected": sec.decision in ("REVIEW", "BLOCK"),
        }

        ts = time.perf_counter()
        should_rag = self._should_call_rag(
            sec_decision=str(sec.decision),
            sec_score=float(sec.score),
            persona=signals.get("persona"),
            context_keywords=list(signals.get("context_keywords") or []),
            entities=entities,
            spoken_entities=spoken_entities,
        )
        timing_ms_by_stage["gate_rag"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        if should_rag:
            rag_out = await self.rag.decide(
                session=session,
                user_text=text,
                company_id=company_id,
                message_id=None,
            )
            signals["rag"] = {
                "decision": rag_out.decision,
                "confidence": rag_out.confidence,
                "rule_keys": rag_out.rule_keys,
                "rationale": rag_out.rationale,
            }
        else:
            signals.pop("rag", None)
        timing_ms_by_stage["rag"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        matches = self.rule_engine.evaluate(
            session=session,
            company_id=company_id,
            entities=entities,
            signals=signals,
        )
        timing_ms_by_stage["rule_eval"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        decision = self.resolver.resolve(matches)
        timing_ms_by_stage["resolve"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        matches = compact_matches(
            matches, final_action=str(decision.final_action).lower()
        )
        timing_ms_by_stage["compact_matches"] = int((time.perf_counter() - ts) * 1000)

        latency_ms = int((time.perf_counter() - t0) * 1000)
        timing_ms_by_stage["total"] = latency_ms

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
            "timing_ms_by_stage": timing_ms_by_stage,
            "risk_score": risk_score,
            "ambiguous": should_rag,
        }
