from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal, Optional
from uuid import UUID

from sqlmodel import Session

from app.core.config import get_settings
from app.llm import LlmTextResult, generate_text_async
from app.rag.models.rag_retrieval_log import RagRetrievalLog
from app.rag.policy_retriever import PolicyRetriever


DecisionType = Literal["ALLOW", "MASK", "BLOCK"]


@dataclass(slots=True)
class RagDecision:
    decision: DecisionType
    confidence: float
    rule_keys: list[str]
    rationale: str


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
        self.llm_provider = str(settings.non_embedding_llm_provider or "ollama").strip().lower()
        default_model = (
            settings.gemini_model
            if self.llm_provider == "gemini"
            else settings.ollama_model
        )
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
        message_id: Optional[UUID],
    ) -> RagDecision:
        t0 = time.perf_counter()

        try:
            chunks = await self.retriever.retrieve(
                session=session,
                query=user_text,
                company_id=company_id,
                message_id=message_id,
                top_k=self.retriever.top_k,
            )
        except Exception:
            return RagDecision(
                decision="ALLOW",
                confidence=0.5,
                rule_keys=[],
                rationale="rag_retrieval_failed",
            )

        contexts = [c.content for c in chunks]
        prompt = self._build_prompt(user_text=user_text, contexts=contexts)

        llm_out: LlmTextResult
        try:
            llm_out = await self._call_llm(prompt)
            raw = llm_out.text
        except Exception:
            return RagDecision(
                decision="ALLOW",
                confidence=0.5,
                rule_keys=[],
                rationale="rag_timeout",
            )

        parsed_ok = True
        parse_error = None

        try:
            obj = self._parse_json(raw)

            decision = str(obj.get("decision", "ALLOW")).upper()
            if decision not in ("ALLOW", "MASK", "BLOCK"):
                decision = "ALLOW"

            confidence = float(obj.get("confidence", 0.6))
            confidence = max(0.0, min(1.0, confidence))

            rule_keys = [str(x) for x in (obj.get("rule_keys") or [])][:10]
            rationale = str(obj.get("rationale") or "")[:200]

            out = RagDecision(
                decision=decision,
                confidence=confidence,
                rule_keys=rule_keys,
                rationale=rationale,
            )

        except Exception as e:
            parsed_ok = False
            parse_error = repr(e)
            out = RagDecision(
                decision="ALLOW",
                confidence=0.5,
                rule_keys=[],
                rationale="parse_failed",
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
                        },
                        "decision": {
                            "decision": out.decision,
                            "confidence": out.confidence,
                            "rule_keys": out.rule_keys,
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
        return await generate_text_async(
            prompt=prompt,
            provider=self.llm_provider,
            model_name=self.llm_model,
            timeout_s=self.settings.non_embedding_llm_timeout_seconds,
        )

    def _build_prompt(self, *, user_text: str, contexts: list[str]) -> str:
        ctx_block = "\n\n---\n\n".join(contexts) if contexts else "(none)"
        return f"""
You are a strict security policy decision engine.

You MUST output ONLY a single valid JSON object.
No markdown. No explanations outside JSON.

Valid decision values: ALLOW, MASK, BLOCK

POLICY CONTEXT:
{ctx_block}

USER MESSAGE:
{user_text}
""".strip()

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
