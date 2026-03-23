# app/decision/scan_engine_local.py
from __future__ import annotations

import re
import time
import unicodedata
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
    _RAG_BLOCK_KEY = "global.security.rag.block"
    _RAG_MASK_KEY = "global.security.rag.mask"
    _RAG_KEY_PREFIX = "global.security.rag."
    _SIMPLE_PII_TYPES = {"PHONE", "EMAIL", "TAX_ID", "CCCD", "CREDIT_CARD"}

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

        dev_kws = {
            "api key",
            "apikey",
            "token",
            "secret",
            "bearer",
            ".env",
            "authorization",
        }
        lowered_kws = {str(k or "").lower() for k in context_keywords}
        if persona == "dev" and (lowered_kws & dev_kws):
            has_secret = any(
                str(getattr(e, "type", "") or "") == "API_SECRET"
                and float(getattr(e, "score", 0.0) or 0.0) >= 0.85
                for e in entities
            )
            if has_secret:
                return False
            # Developer context mentioning key/token/secret should be reviewed by RAG.
            return True

        return False

    def _is_rag_rule_key(self, stable_key: Any) -> bool:
        key = str(stable_key or "").strip().lower()
        return key.startswith(self._RAG_KEY_PREFIX)

    def _action_name(self, action: Any) -> str:
        if hasattr(action, "value"):
            return str(getattr(action, "value") or "").strip().lower()
        return str(action or "").strip().lower()

    def _is_simple_pii_only(self, entities: list[Any]) -> bool:
        if not entities:
            return False

        has_supported = False
        for e in entities:
            etype = str(getattr(e, "type", "") or "").strip().upper()
            if not etype:
                continue
            has_supported = True
            if etype not in self._SIMPLE_PII_TYPES:
                return False

        return has_supported

    def _fold_text(self, text: str) -> str:
        raw = str(text or "").lower().replace("\u0111", "d")
        normalized = unicodedata.normalize("NFKD", raw)
        no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", no_marks).strip()

    def _match_exact_terms_in_text(
        self,
        *,
        text: str,
        exact_terms: list[str],
        limit: int = 20,
        min_length: int = 2,
    ) -> list[str]:
        if not exact_terms:
            return []

        raw_text = str(text or "").lower()
        fold_text = self._fold_text(text)
        out: list[str] = []
        seen: set[str] = set()
        safe_limit = max(1, int(limit))

        for term in exact_terms:
            normalized_term = str(term or "").strip().lower()
            if len(normalized_term) < max(1, int(min_length)):
                continue
            if normalized_term in seen:
                continue

            fold_term = self._fold_text(normalized_term)
            if normalized_term in raw_text or (fold_term and fold_term in fold_text):
                seen.add(normalized_term)
                out.append(normalized_term)
                if len(out) >= safe_limit:
                    break
        return out

    def _merge_context_keywords(
        self,
        *,
        context_keywords: list[str],
        extra_keywords: list[str],
        limit: int = 24,
    ) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()

        for value in list(context_keywords) + list(extra_keywords):
            item = str(value or "").strip().lower()
            if not item or item in seen:
                continue
            seen.add(item)
            out.append(item)
            if len(out) >= max(1, int(limit)):
                break
        return out

    def _get_effective_rag_toggles(
        self,
        *,
        session: Session,
        company_id: Optional[UUID],
        user_id: Optional[UUID],
    ) -> tuple[bool, bool]:
        runtime_rules = self.rule_engine.load_rules(
            session=session,
            company_id=company_id,
            user_id=user_id,
        )
        keys = {str(r.stable_key) for r in runtime_rules}
        return (self._RAG_BLOCK_KEY in keys, self._RAG_MASK_KEY in keys)

    async def scan(
        self,
        *,
        session: Session,
        text: str,
        company_id: Optional[UUID],
        user_id: Optional[UUID] = None,
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
        timing_ms_by_stage["normalize_entities"] = int(
            (time.perf_counter() - ts) * 1000
        )

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
        matched_exact_terms = self._match_exact_terms_in_text(
            text=text,
            exact_terms=overrides.exact_terms,
        )
        signals["context_keywords"] = self._merge_context_keywords(
            context_keywords=list(signals.get("context_keywords") or []),
            extra_keywords=matched_exact_terms,
        )
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
        should_rag_gate = self._should_call_rag(
            sec_decision=str(sec.decision),
            sec_score=float(sec.score),
            persona=signals.get("persona"),
            context_keywords=list(signals.get("context_keywords") or []),
            entities=entities,
            spoken_entities=spoken_entities,
        )
        timing_ms_by_stage["gate_rag"] = int((time.perf_counter() - ts) * 1000)

        # Phase 1: evaluate local/policy rules without rag.* rules.
        ts = time.perf_counter()
        phase1_matches = self.rule_engine.evaluate(
            session=session,
            company_id=company_id,
            user_id=user_id,
            entities=entities,
            signals=signals,
        )
        phase1_matches = [
            m for m in phase1_matches if not self._is_rag_rule_key(m.stable_key)
        ]
        timing_ms_by_stage["rule_eval_phase1"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        phase1_decision = self.resolver.resolve(phase1_matches)
        timing_ms_by_stage["resolve_phase1"] = int((time.perf_counter() - ts) * 1000)

        if self._action_name(phase1_decision.final_action) != "allow":
            signals.pop("rag", None)
            ts = time.perf_counter()
            phase1_matches = compact_matches(
                phase1_matches,
                final_action=self._action_name(phase1_decision.final_action),
            )
            timing_ms_by_stage["compact_matches"] = int(
                (time.perf_counter() - ts) * 1000
            )
            timing_ms_by_stage["rag"] = 0
            timing_ms_by_stage["rule_eval"] = timing_ms_by_stage["rule_eval_phase1"]
            timing_ms_by_stage["resolve"] = timing_ms_by_stage["resolve_phase1"]

            latency_ms = int((time.perf_counter() - t0) * 1000)
            timing_ms_by_stage["total"] = latency_ms

            max_entity = max(
                [float(getattr(e, "score", 0.0)) for e in entities], default=0.0
            )
            risk_score = min(
                1.0, max_entity + float(signals.get("risk_boost", 0.0) or 0.0)
            )

            return {
                "entities": entities,
                "signals": signals,
                "matches": phase1_matches,
                "final_action": phase1_decision.final_action,
                "latency_ms": latency_ms,
                "timing_ms_by_stage": timing_ms_by_stage,
                "risk_score": risk_score,
                "ambiguous": False,
            }

        ts = time.perf_counter()
        rag_block_on, rag_mask_on = self._get_effective_rag_toggles(
            session=session,
            company_id=company_id,
            user_id=user_id,
        )
        timing_ms_by_stage["resolve_rag_toggles"] = int(
            (time.perf_counter() - ts) * 1000
        )

        simple_pii_guard = bool(
            (len(phase1_matches) == 0)
            and (str(sec.decision).upper() == "ALLOW")
            and self._is_simple_pii_only(entities)
        )

        should_call_rag = bool(
            should_rag_gate
            and (rag_block_on or rag_mask_on)
            and not simple_pii_guard
        )

        ts = time.perf_counter()
        if should_call_rag:
            rag_out = await self.rag.decide(
                session=session,
                user_text=text,
                company_id=company_id,
                message_id=None,
            )
            raw_rag_decision = str(rag_out.decision).upper()
            effective_rag_decision = raw_rag_decision
            if raw_rag_decision == "BLOCK" and not rag_block_on:
                effective_rag_decision = "ALLOW"
            if raw_rag_decision == "MASK" and not rag_mask_on:
                effective_rag_decision = "ALLOW"
            signals["rag"] = {
                "decision": effective_rag_decision,
                "decision_raw": raw_rag_decision,
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
            user_id=user_id,
            entities=entities,
            signals=signals,
        )
        timing_ms_by_stage["rule_eval"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        decision = self.resolver.resolve(matches)
        timing_ms_by_stage["resolve"] = int((time.perf_counter() - ts) * 1000)

        ts = time.perf_counter()
        matches = compact_matches(matches, final_action=self._action_name(decision.final_action))
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
            "ambiguous": should_call_rag,
        }

