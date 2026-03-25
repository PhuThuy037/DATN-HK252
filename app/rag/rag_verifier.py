from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal, Optional
from uuid import UUID

from sqlmodel import Session

from app.common.enums import RuleScope
from app.core.config import get_settings
from app.llm import LlmTextResult, generate_text_async
from app.rag.models.rag_retrieval_log import RagRetrievalLog
from app.rag.policy_retriever import PolicyRetriever
from app.rule_embedding.service import retrieve_related_rules_for_runtime


DecisionType = Literal["ALLOW", "MASK", "BLOCK"]


@dataclass(slots=True)
class RagDecision:
    decision: DecisionType
    confidence: float
    rule_keys: list[str]
    rationale: str
    candidate_rule_keys: list[str]


class RagVerifier:
    def __init__(
        self,
        *,
        llm_model: Optional[str] = None,
        embed_model: str = "mxbai-embed-large",
        embedding_dim: int = 1024,
        top_k: int = 5,
    ):
        settings = get_settings()

        self.settings = settings
        self.llm_provider = str(settings.non_embedding_llm_provider or "groq").strip().lower()
        default_model_by_provider = {
            "groq": settings.groq_model,
            "gemini": settings.gemini_model,
            "ollama": settings.ollama_model,
        }
        default_model = default_model_by_provider.get(self.llm_provider, settings.groq_model)
        self.llm_model = llm_model or default_model

        self.retriever = PolicyRetriever(
            embed_model=embed_model,
            embedding_dim=embedding_dim,
            top_k=top_k,
        )

    async def decide(
        self,
        *,
        session: Session,
        user_text: str,
        company_id: Optional[UUID],
        user_id: Optional[UUID],
        message_id: Optional[UUID],
        runtime_scope: RuleScope = RuleScope.prompt,
    ) -> RagDecision:
        t0 = time.perf_counter()
        chunks = []
        policy_error = None
        rule_error = None

        try:
            chunks = await self.retriever.retrieve(
                session=session,
                query=user_text,
                company_id=company_id,
                message_id=message_id,
                top_k=self.retriever.top_k,
                log=False,
            )
        except Exception as exc:
            policy_error = repr(exc)

        contexts = [str(c.content or "").strip() for c in chunks if str(c.content or "").strip()]
        try:
            related_rules = retrieve_related_rules_for_runtime(
                session=session,
                query=user_text,
                company_id=company_id,
                user_id=user_id,
                runtime_scope=runtime_scope,
                limit=max(3, int(self.settings.rule_duplicate_top_k)),
            )
        except Exception as exc:
            rule_error = repr(exc)
            related_rules = []
        candidate_rule_keys = [str(item.get("stable_key") or "") for item in related_rules]

        if not contexts and not related_rules:
            return RagDecision(
                decision="ALLOW",
                confidence=0.6,
                rule_keys=[],
                rationale="no_policy_or_rule_context",
                candidate_rule_keys=[],
            )
        prompt = self._build_prompt(
            user_text=user_text,
            contexts=contexts,
            related_rules=related_rules,
        )

        llm_out: LlmTextResult
        raw = ""
        try:
            llm_out = await self._call_llm(prompt)
            raw = llm_out.text
        except Exception:
            return RagDecision(
                decision="ALLOW",
                confidence=0.5,
                rule_keys=[],
                rationale="rag_timeout",
                candidate_rule_keys=candidate_rule_keys,
            )

        parsed_ok = True
        parse_error = None
        filtered_rule_keys: list[str] = []

        try:
            obj = self._parse_json(raw)

            decision = str(obj.get("decision", "ALLOW")).upper()
            if decision not in ("ALLOW", "MASK", "BLOCK"):
                decision = "ALLOW"

            confidence = float(obj.get("confidence", 0.6))
            confidence = max(0.0, min(1.0, confidence))

            rule_keys = [str(x) for x in (obj.get("rule_keys") or [])][:10]
            filtered_rule_keys = self._filter_rule_keys(
                rule_keys=rule_keys,
                related_rules=related_rules,
            )
            rationale = str(obj.get("rationale") or "")[:200]

            out = RagDecision(
                decision=decision,
                confidence=confidence,
                rule_keys=filtered_rule_keys,
                rationale=rationale,
                candidate_rule_keys=candidate_rule_keys,
            )

        except Exception as e:
            parsed_ok = False
            parse_error = repr(e)
            out = RagDecision(
                decision="ALLOW",
                confidence=0.5,
                rule_keys=[],
                rationale="parse_failed",
                candidate_rule_keys=candidate_rule_keys,
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        try:
            session.add(
                RagRetrievalLog(
                    message_id=message_id,
                    query=user_text[:2000],
                    top_k=self.retriever.top_k,
                    latency_ms=latency_ms,
                    results_json={
                        "meta": {
                            "llm_model": llm_out.model,
                            "llm_provider": llm_out.provider,
                            "llm_fallback_used": llm_out.fallback_used,
                            "embed_model": getattr(self.retriever, "embed_model", None),
                            "parsed_ok": parsed_ok,
                            "parse_error": parse_error,
                            "policy_error": policy_error,
                            "rule_error": rule_error,
                            "runtime_scope": runtime_scope.value,
                        },
                        "policy_chunks": [
                            {"chunk_id": str(c.chunk_id), "sim": float(c.sim)}
                            for c in chunks
                        ],
                        "related_rules": related_rules,
                        "decision": {
                            "decision": out.decision,
                            "confidence": out.confidence,
                            "rule_keys": out.rule_keys,
                            "candidate_rule_keys": out.candidate_rule_keys,
                            "rationale": out.rationale,
                        },
                        "prompt": prompt[:6000],
                        "raw": raw[:6000],
                    },
                )
            )
            session.commit()
        except Exception:
            session.rollback()

        return out

    async def _call_llm(self, prompt: str) -> LlmTextResult:
        timeout_s = min(6.0, float(self.settings.non_embedding_llm_timeout_seconds))
        return await generate_text_async(
            prompt=prompt,
            provider=self.llm_provider,
            model_name=self.llm_model,
            timeout_s=timeout_s,
            fast_fallback=True,
        )

    def _build_prompt(
        self,
        *,
        user_text: str,
        contexts: list[str],
        related_rules: list[dict[str, Any]],
    ) -> str:
        ctx_block = "\n\n---\n\n".join(contexts) if contexts else "(none)"
        rules_block = (
            json.dumps(related_rules, ensure_ascii=False, indent=2)
            if related_rules
            else "[]"
        )
        allowed_rule_keys = json.dumps(
            [str(item.get("stable_key") or "") for item in related_rules],
            ensure_ascii=False,
        )
        return f"""
You are a strict security policy decision engine.

You MUST output ONLY a single valid JSON object.
No markdown. No explanations outside JSON.

Valid decision values: ALLOW, MASK, BLOCK

You MUST use both POLICY CONTEXT and RELATED RULES when they are available.
Only choose rule_keys from ALLOWED RULE KEYS.
If no candidate rule clearly supports your decision, return "rule_keys": [].
Treat rag_mode="verify" as direct verification evidence.
Treat rag_mode="explain" as contextual grounding only.

Return JSON with exactly these fields:
{{"decision":"ALLOW|MASK|BLOCK","confidence":0.0,"rule_keys":[],"rationale":"short string"}}

POLICY CONTEXT:
{ctx_block}

RELATED RULES:
{rules_block}

ALLOWED RULE KEYS:
{allowed_rule_keys}

USER MESSAGE:
{user_text}
""".strip()

    def _filter_rule_keys(
        self,
        *,
        rule_keys: list[str],
        related_rules: list[dict[str, Any]],
    ) -> list[str]:
        allowed = {
            str(item.get("stable_key") or "").strip().lower(): str(item.get("stable_key") or "").strip()
            for item in related_rules
            if str(item.get("stable_key") or "").strip()
        }
        out: list[str] = []
        seen: set[str] = set()
        for raw_key in rule_keys:
            normalized = str(raw_key or "").strip().lower()
            if not normalized or normalized in seen:
                continue
            canonical = allowed.get(normalized)
            if not canonical:
                continue
            seen.add(normalized)
            out.append(canonical)
        return out

    def _parse_json(self, raw: str) -> dict[str, Any]:
        raw = raw.strip()
        try:
            return json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(raw[start : end + 1])
            raise
