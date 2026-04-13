from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity
from app.core.config import get_settings
from app.llm import generate_text_sync
from app.rule.model import Rule
from app.suggestion.literal_detector import LiteralDetectionResult
from app.suggestion.schemas import (
    RuleSuggestionDraftContextTerm,
    RuleSuggestionDraftPayload,
    RuleSuggestionDraftRule,
)
from app.suggestion.suggestion_extractor import (
    HybridExtractionResult,
    PromptKeywordBundle,
    _RETRIEVAL_STOP_WORDS,
    _extract_meaningful_prompt_phrases,
    _extract_prompt_context_phrases,
    _extract_target_families,
    extract_hybrid,
)


def _svc() -> Any:
    from app.suggestion import service

    return service


def _run_coro_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("cannot_block_on_running_event_loop")


def _empty_extraction() -> HybridExtractionResult:
    return HybridExtractionResult(
        target_entities=[],
        business_phrases=[],
        context_modifiers=[],
        helper_tokens=[],
    )


def _safe_extract_hybrid(prompt: str) -> HybridExtractionResult:
    try:
        extraction = extract_hybrid(prompt)
    except Exception:
        return _empty_extraction()
    if not isinstance(extraction, HybridExtractionResult):
        return _empty_extraction()
    return extraction


def _extraction_target_phrases(
    prompt: str,
    *,
    extraction: HybridExtractionResult | None,
    limit: int,
) -> list[str]:
    safe_limit = max(1, min(int(limit), 32))
    values = _svc()._unique_phrase_values(list((extraction or _empty_extraction()).target_entities))
    if values:
        return values[:safe_limit]
    return _svc()._extract_target_phrases(prompt, limit=safe_limit)


def _extraction_business_phrases(
    prompt: str,
    *,
    extraction: HybridExtractionResult | None,
    limit: int,
) -> list[str]:
    safe_limit = max(1, min(int(limit), 32))
    values = _svc()._unique_phrase_values(list((extraction or _empty_extraction()).business_phrases))
    if values:
        return values[:safe_limit]
    return _svc()._extract_business_noun_phrases(prompt, limit=safe_limit)


def _extraction_context_phrases(
    prompt: str,
    *,
    extraction: HybridExtractionResult | None,
    limit: int,
) -> list[str]:
    safe_limit = max(1, min(int(limit), 32))
    extraction_value = extraction or _empty_extraction()
    values = _svc()._unique_phrase_values(
        list(extraction_value.business_phrases) + list(extraction_value.context_modifiers)
    )
    if values:
        return values[:safe_limit]
    return _svc()._extract_prompt_context_phrases(prompt, limit=safe_limit)


def _extraction_target_families(
    prompt: str,
    *,
    extraction: HybridExtractionResult | None,
) -> set[str]:
    families: set[str] = set()
    for phrase in list((extraction or _empty_extraction()).target_entities):
        families.update(_svc()._extract_target_families(phrase))
    if families:
        return families
    return _svc()._extract_target_families(prompt)


def _prompt_keyword_bundle_from_extraction(
    prompt: str,
    *,
    extraction: HybridExtractionResult | None,
    limit: int,
) -> PromptKeywordBundle:
    safe_limit = max(1, min(int(limit), 32))
    fallback_bundle = _svc()._prompt_keywords(prompt, limit=safe_limit)
    phrases = _extraction_target_phrases(prompt, extraction=extraction, limit=safe_limit)
    if not phrases:
        phrases = _extraction_context_phrases(prompt, extraction=extraction, limit=safe_limit)
    helper_tokens = _svc()._unique_phrase_values(
        list((extraction or _empty_extraction()).helper_tokens)
    )
    if not helper_tokens:
        helper_tokens = list(fallback_bundle.get("tokens") or [])
    return {
        "phrases": list(phrases[:safe_limit]),
        "tokens": list(helper_tokens[: max(2, min(64, safe_limit * 3))]),
    }


def _build_minimal_safe_prompt_draft(
    *,
    prompt: str,
    extraction: HybridExtractionResult | None = None,
) -> RuleSuggestionDraftPayload:
    action = _svc()._action_hint_from_prompt(prompt)
    stable_suffix = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    target_phrases = _extraction_target_phrases(prompt, extraction=extraction, limit=2)
    business_phrases = _extraction_business_phrases(prompt, extraction=extraction, limit=8)
    context_phrases = _extraction_context_phrases(prompt, extraction=extraction, limit=8)

    keywords = _svc()._unique_phrase_values(target_phrases)[:2]
    if not keywords:
        fallback_keywords = _svc()._remove_redundant_subphrases(
            [
                value
                for value in (business_phrases + context_phrases)
                if not _svc()._is_generic_modifier_phrase(value)
            ],
        )
        keywords = fallback_keywords[:1]
    if not keywords:
        token_fallback = list(
            _prompt_keyword_bundle_from_extraction(prompt, extraction=extraction, limit=8).get(
                "tokens"
            )
            or []
        )
        safe_tokens = [t for t in token_fallback if len(str(t or "").strip()) >= 4]
        keywords = [safe_tokens[0]] if safe_tokens else ["context"]

    support_candidates = _svc()._remove_redundant_subphrases(
        business_phrases + context_phrases,
        protected=set(_svc()._GENERIC_MODIFIER_PHRASES),
    )
    keyword_folds = {_svc()._fold_text(value) for value in keywords if _svc()._fold_text(value)}
    support_terms = [
        value for value in support_candidates if _svc()._fold_text(value) not in keyword_folds
    ][:6]

    rule = RuleSuggestionDraftRule(
        stable_key=f"personal.custom.suggested.{stable_suffix}",
        name="Suggested prompt policy",
        description=f"Auto-generated suggestion from prompt: {prompt[:180]}",
        scope=RuleScope.prompt,
        conditions={
            "all": [
                {
                    "signal": {
                        "field": "context_keywords",
                        "any_of": keywords,
                    }
                }
            ]
        },
        action=action,
        severity=RuleSeverity.high if action == RuleAction.block else RuleSeverity.medium,
        priority=90 if action == RuleAction.block else 70,
        rag_mode=RagMode.off,
        enabled=True,
    )
    terms = [
        RuleSuggestionDraftContextTerm(
            entity_type="CUSTOM_SECRET",
            term=_svc()._normalize_phrase_text(value),
            lang="vi",
            weight=1.0,
            window_1=60,
            window_2=20,
            enabled=True,
        )
        for value in support_terms
        if _svc()._normalize_phrase_text(value)
    ]
    draft = RuleSuggestionDraftPayload(rule=rule, context_terms=terms)
    drafted, _meta = _svc()._enforce_keyword_context_role_contract(
        prompt=prompt,
        draft=draft,
        prompt_keyword_bundle=_prompt_keyword_bundle_from_extraction(
            prompt,
            extraction=extraction,
            limit=16,
        ),
    )
    return _svc()._sanitize_debug_placeholder_text(prompt=prompt, draft=drafted)


def _build_exact_secret_draft(
    *,
    prompt: str,
    token_terms: list[str],
    action: RuleAction,
    stable_suffix: str,
) -> RuleSuggestionDraftPayload:
    normalized_terms: list[str] = []
    seen: set[str] = set()
    for token in token_terms:
        t = str(token or "").strip().lower()
        if not t or t in seen:
            continue
        seen.add(t)
        normalized_terms.append(t)
    if not normalized_terms:
        normalized_terms = ["internal-secret"]

    primary = normalized_terms[0]
    rule = RuleSuggestionDraftRule(
        stable_key=f"personal.custom.suggested.{stable_suffix}",
        name=f"Protect internal token {primary}",
        description=f"Protect exact internal code/token from prompt: {prompt[:180]}",
        scope=RuleScope.prompt,
        conditions={
            "all": [
                {"signal": {"field": "context_keywords", "any_of": normalized_terms[:4]}},
            ]
        },
        action=action,
        severity=RuleSeverity.high if action == RuleAction.block else RuleSeverity.medium,
        priority=150 if action == RuleAction.block else 130,
        rag_mode=RagMode.off,
        enabled=True,
    )
    terms: list[RuleSuggestionDraftContextTerm] = []
    for term in normalized_terms[:4]:
        terms.append(
            RuleSuggestionDraftContextTerm(
                entity_type="INTERNAL_CODE",
                term=term,
                lang="vi",
                weight=1.0,
                window_1=80,
                window_2=24,
                enabled=True,
            )
        )
    return RuleSuggestionDraftPayload(rule=rule, context_terms=terms)


def _build_payroll_external_email_draft(
    *,
    prompt: str,
    action: RuleAction,
    stable_suffix: str,
) -> RuleSuggestionDraftPayload:
    payroll_terms = ["payroll", "salary", "luong", "bang luong"]
    external_terms = ["gmail", "personal email", "email ngoai cong ty", "external email"]
    rule = RuleSuggestionDraftRule(
        stable_key=f"personal.custom.suggested.{stable_suffix}",
        name=f"Protect payroll to external email ({action.value})",
        description=f"Protect payroll/salary data from external or personal email sharing: {prompt[:180]}",
        scope=RuleScope.prompt,
        conditions={
            "all": [
                {"signal": {"field": "context_keywords", "any_of": payroll_terms}},
                {"signal": {"field": "context_keywords", "any_of": external_terms}},
            ]
        },
        action=action,
        severity=RuleSeverity.high if action == RuleAction.block else RuleSeverity.medium,
        priority=155 if action == RuleAction.block else 135,
        rag_mode=RagMode.off,
        enabled=True,
    )
    terms = [
        RuleSuggestionDraftContextTerm(
            entity_type="PERSONA_OFFICE",
            term=t,
            lang="vi",
            weight=1.0,
            window_1=80,
            window_2=24,
            enabled=True,
        )
        for t in (payroll_terms + external_terms)
    ]
    return RuleSuggestionDraftPayload(rule=rule, context_terms=terms)


def _build_persona_signal_draft(
    *,
    prompt: str,
    persona: str,
    keywords: list[str],
    action: RuleAction,
    stable_suffix: str,
) -> RuleSuggestionDraftPayload:
    stable_key = f"personal.custom.suggested.{stable_suffix}"
    if persona == "office":
        rule_name = f"Suggested office context {action.value}"
        risk_threshold = 0.10
        priority = 105 if action == RuleAction.block else 95
        ctx_entity = "PERSONA_OFFICE"
    elif persona == "dev":
        rule_name = f"Suggested dev context {action.value}"
        risk_threshold = 0.15
        priority = 105 if action == RuleAction.block else 95
        ctx_entity = "PERSONA_DEV"
    else:
        rule_name = f"Suggested finance context {action.value}"
        risk_threshold = 0.20
        priority = 130 if action == RuleAction.block else 110
        ctx_entity = "PERSONA_FINANCE"
    keyword_values = keywords[:6] or ["context"]

    rule = RuleSuggestionDraftRule(
        stable_key=stable_key,
        name=rule_name,
        description=f"Auto-generated from prompt: {prompt[:180]}",
        scope=RuleScope.prompt,
        conditions={
            "all": [
                {"signal": {"field": "persona", "equals": persona}},
                {"signal": {"field": "risk_boost", "gte": risk_threshold}},
                {"signal": {"field": "context_keywords", "any_of": keyword_values}},
            ]
        },
        action=action,
        severity=RuleSeverity.medium if action != RuleAction.block else RuleSeverity.high,
        priority=priority,
        rag_mode=RagMode.off,
        enabled=True,
    )

    ctx_terms = [
        RuleSuggestionDraftContextTerm(entity_type=ctx_entity, term=k, lang="vi")
        for k in keyword_values[:3]
    ]
    return RuleSuggestionDraftPayload(rule=rule, context_terms=ctx_terms)


def _build_generic_prompt_keyword_draft(
    *,
    prompt: str,
    action: RuleAction,
    stable_suffix: str,
    phrases: list[str],
    extraction: HybridExtractionResult | None = None,
) -> RuleSuggestionDraftPayload:
    keyword_candidates = list(phrases) or _extraction_target_phrases(
        prompt,
        extraction=extraction,
        limit=6,
    )
    if not keyword_candidates:
        keyword_candidates = _extraction_business_phrases(prompt, extraction=extraction, limit=6)
    if not keyword_candidates:
        keyword_candidates = _extraction_context_phrases(prompt, extraction=extraction, limit=6)
    keyword_values = _svc()._sanitize_context_keyword_values(
        list(keyword_candidates),
        fallback_phrases=list(keyword_candidates),
    )
    keyword_values = keyword_values[:6] or ["context"]
    rule = RuleSuggestionDraftRule(
        stable_key=f"personal.custom.suggested.{stable_suffix}",
        name=f"Suggested prompt keyword {action.value}",
        description=f"Auto-generated from prompt keyword signals: {prompt[:180]}",
        scope=RuleScope.prompt,
        conditions={
            "all": [
                {"signal": {"field": "context_keywords", "any_of": keyword_values}},
            ]
        },
        action=action,
        severity=RuleSeverity.medium if action != RuleAction.block else RuleSeverity.high,
        priority=90 if action == RuleAction.block else 70,
        rag_mode=RagMode.off,
        enabled=True,
    )
    return RuleSuggestionDraftPayload(rule=rule, context_terms=[])


def _build_literal_refinement_draft(
    *,
    prompt: str,
    action: RuleAction,
    stable_suffix: str,
    extraction: HybridExtractionResult | None = None,
) -> RuleSuggestionDraftPayload:
    prompt_keywords = _prompt_keyword_bundle_from_extraction(
        prompt,
        extraction=extraction,
        limit=6,
    )
    keyword_values = list(prompt_keywords.get("phrases") or [])
    if not keyword_values:
        keyword_values = _extraction_context_phrases(prompt, extraction=extraction, limit=6)
    keyword_values = _svc()._sanitize_context_keyword_values(
        list(keyword_values),
        fallback_phrases=list(keyword_values),
    )
    keyword_values = keyword_values[:6] or ["context"]

    context_terms = [
        RuleSuggestionDraftContextTerm(
            entity_type="CUSTOM_SECRET",
            term=_svc()._normalize_phrase_text(term),
            lang="vi",
            weight=1.0,
            window_1=60,
            window_2=20,
            enabled=True,
        )
        for term in _extraction_context_phrases(prompt, extraction=extraction, limit=4)
        if _svc()._normalize_phrase_text(term)
    ]

    rule = RuleSuggestionDraftRule(
        stable_key=f"personal.custom.suggested.{stable_suffix}",
        name="Suggested prompt policy",
        description=f"Auto-generated suggestion from prompt: {prompt[:180]}",
        scope=RuleScope.prompt,
        conditions={
            "all": [
                {"signal": {"field": "context_keywords", "any_of": keyword_values}},
            ]
        },
        action=action,
        severity=RuleSeverity.low,
        priority=40,
        rag_mode=RagMode.off,
        enabled=True,
    )
    return RuleSuggestionDraftPayload(rule=rule, context_terms=context_terms)


def _fallback_generate(
    prompt: str,
    *,
    extraction: HybridExtractionResult | None = None,
) -> RuleSuggestionDraftPayload:
    p = prompt.lower()
    action = _svc()._action_hint_from_prompt(prompt)
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    literal_detection = _svc()._literal_detection(prompt, limit=8)
    code_tokens = list(literal_detection.candidate_tokens[:4])

    office_hr_keys = [
        "luong",
        "lương",
        "hop dong",
        "hợp đồng",
        "nhan su",
        "nhân sự",
        "hr",
    ]
    dev_infra_keys = ["docker", "kubernetes", "github", "helm", "ci cd", "devops"]
    finance_keys = [
        "tai chinh",
        "bao cao tai chinh",
        "doanh thu",
        "loi nhuan",
        "ke toan",
        "revenue",
        "profit",
    ]

    if _svc()._is_payroll_external_email_prompt(prompt):
        return _build_payroll_external_email_draft(
            prompt=prompt,
            action=action,
            stable_suffix=h,
        )

    if literal_detection.known_pii_type:
        entity_type = str(literal_detection.known_pii_type).strip().upper()
        rule_name, severity, priority, min_score = _svc()._known_pii_fallback_profile(
            entity_type=entity_type,
            action=action,
        )
        condition_leaf: dict[str, Any] = {"entity_type": entity_type}
        if min_score > 0:
            condition_leaf["min_score"] = float(min_score)
        stable_key = f"personal.custom.suggested.{h}"
        return RuleSuggestionDraftPayload(
            rule=RuleSuggestionDraftRule(
                stable_key=stable_key,
                name=rule_name,
                description=f"Auto-generated from prompt: {prompt[:180]}",
                scope=RuleScope.prompt,
                conditions={"any": [condition_leaf]},
                action=action,
                severity=severity,
                priority=priority,
                rag_mode=RagMode.off,
                enabled=True,
            ),
            context_terms=[],
        )

    if literal_detection.decision_hint == "INTERNAL_CODE" and code_tokens:
        return _build_exact_secret_draft(
            prompt=prompt,
            token_terms=code_tokens,
            action=action,
            stable_suffix=h,
        )

    if literal_detection.intent_literal and (not literal_detection.known_pii_type) and (not code_tokens):
        return _build_literal_refinement_draft(
            prompt=prompt,
            action=action,
            stable_suffix=h,
            extraction=extraction,
        )

    if _svc()._has_any(p, office_hr_keys):
        matched = [k for k in office_hr_keys if k in p][:4]
        return _build_persona_signal_draft(
            prompt=prompt,
            persona="office",
            keywords=matched or ["nhan su", "hop dong", "luong"],
            action=action,
            stable_suffix=h,
        )

    if _svc()._has_any(p, dev_infra_keys):
        matched = [k for k in dev_infra_keys if k in p][:4]
        return _build_persona_signal_draft(
            prompt=prompt,
            persona="dev",
            keywords=matched or ["docker", "kubernetes", "github"],
            action=action,
            stable_suffix=h,
        )

    if _svc()._is_finance_prompt(p) and (not _svc()._mentions_tax_id(p)):
        matched = [k for k in finance_keys if k in p][:4]
        return _build_persona_signal_draft(
            prompt=prompt,
            persona="finance",
            keywords=matched or ["bao cao tai chinh", "doanh thu", "loi nhuan"],
            action=action,
            stable_suffix=h,
        )

    keyword_bundle = _prompt_keyword_bundle_from_extraction(
        prompt,
        extraction=extraction,
        limit=6,
    )
    keyword_fallback = list(code_tokens)
    if not keyword_fallback:
        keyword_fallback = _extraction_target_phrases(prompt, extraction=extraction, limit=6)
    if not keyword_fallback:
        keyword_fallback = list(keyword_bundle.get("phrases") or [])
    if not keyword_fallback:
        keyword_fallback = _extraction_business_phrases(prompt, extraction=extraction, limit=6)
    if not keyword_fallback and literal_detection.top_token:
        keyword_fallback = [literal_detection.top_token]
    return _build_generic_prompt_keyword_draft(
        prompt=prompt,
        action=action,
        stable_suffix=h,
        phrases=keyword_fallback or ["context"],
        extraction=extraction,
    )


def _tokenize_for_score(text: str) -> set[str]:
    folded = _svc()._fold_text(text or "")
    parts = re.split(r"[^a-zA-Z0-9_]+", folded)
    return {p for p in parts if len(p) >= 2 and p not in _RETRIEVAL_STOP_WORDS}


def _jaccard_score(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union <= 0:
        return 0.0
    return float(inter / union)


def _rule_reference_text(rule: Rule) -> str:
    match_mode = getattr(rule, "match_mode", None)
    if hasattr(match_mode, "value"):
        match_mode = str(getattr(match_mode, "value"))
    match_mode_text = str(match_mode or "strict_keyword")
    return "\n".join(
        [
            f"stable_key: {rule.stable_key}",
            f"name: {rule.name}",
            f"description: {rule.description or ''}",
            f"scope: {rule.scope.value}",
            f"action: {rule.action.value}",
            f"severity: {rule.severity.value}",
            f"priority: {int(rule.priority)}",
            f"match_mode: {match_mode_text}",
            f"rag_mode: {rule.rag_mode.value}",
            f"conditions: {json.dumps(rule.conditions, sort_keys=True, ensure_ascii=False)}",
        ]
    )


def _build_rule_references(
    *,
    session: Session,
    company_id: UUID,
    prompt: str,
    limit: int = 8,
    extraction: HybridExtractionResult | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 20))
    rows = list(
        session.exec(
            select(Rule)
            .where((Rule.company_id.is_(None)) | (Rule.company_id == company_id))
            .where(Rule.enabled.is_(True))
        ).all()
    )
    prompt_tokens = _tokenize_for_score(prompt)
    prompt_target_phrases = _extraction_target_phrases(prompt, extraction=extraction, limit=6)
    prompt_target_families = _extraction_target_families(prompt, extraction=extraction)
    prompt_target_phrases_folded = [
        _svc()._fold_text(phrase) for phrase in prompt_target_phrases if _svc()._fold_text(phrase)
    ]

    scored: list[tuple[float, int, Rule]] = []
    for row in rows:
        rule_text = _rule_reference_text(row)
        rule_text_folded = _svc()._fold_text(rule_text)
        score = _jaccard_score(prompt_tokens, _tokenize_for_score(rule_text))
        if prompt_target_phrases_folded:
            phrase_hits = sum(
                1
                for phrase in prompt_target_phrases_folded
                if _svc()._contains_prompt_keyword(
                    folded_prompt=rule_text_folded,
                    keyword=phrase,
                )
            )
            if phrase_hits > 0:
                score += 0.40 + (0.10 * min(phrase_hits - 1, 2))
            else:
                score -= 0.15

        rule_target_families = _svc()._extract_target_families(rule_text)
        if prompt_target_families and rule_target_families:
            if not (prompt_target_families & rule_target_families):
                continue
            score += 0.18
        if score <= 0.0:
            continue
        scored.append((score, int(row.priority), row))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    out: list[dict[str, Any]] = []
    for score, _priority, row in scored[:safe_limit]:
        out.append(
            {
                "rule_id": str(row.id),
                "stable_key": row.stable_key,
                "name": row.name,
                "description": row.description,
                "scope": row.scope.value,
                "action": row.action.value,
                "severity": row.severity.value,
                "priority": int(row.priority),
                "match_mode": str(
                    getattr(getattr(row, "match_mode", None), "value", None)
                    or getattr(row, "match_mode", None)
                    or "strict_keyword"
                ),
                "rag_mode": row.rag_mode.value,
                "conditions": row.conditions,
                "origin": "global_default" if row.company_id is None else "personal_rule",
                "prompt_overlap_score": round(float(score), 4),
            }
        )
    return out


class SuggestionContextRetriever:
    def __init__(
        self,
        *,
        session: Session,
        company_id: UUID,
    ) -> None:
        self.session = session
        self.company_id = company_id
        self.policy_retriever: Any | None = None
        try:
            from app.rag.policy_retriever import PolicyRetriever

            self.policy_retriever = PolicyRetriever(
                embed_model=_svc()._SUGGESTION_POLICY_EMBED_MODEL,
                embedding_dim=_svc()._SUGGESTION_POLICY_EMBED_DIM,
                top_k=3,
            )
        except Exception:
            self.policy_retriever = None

    def retrieve_policy_chunks(
        self,
        prompt: str,
        user_id: UUID,
        top_k: int = 3,
        extraction: HybridExtractionResult | None = None,
    ) -> list[dict[str, Any]]:
        _ = user_id
        query = str(prompt or "").strip()
        if not query:
            return []
        if self.policy_retriever is None:
            return []
        safe_top_k = max(1, min(int(top_k), 10))
        try:
            chunks = _run_coro_sync(
                self.policy_retriever.retrieve(
                    session=self.session,
                    query=query,
                    company_id=self.company_id,
                    message_id=None,
                    top_k=safe_top_k,
                    log=False,
                )
            )
        except Exception:
            return []
        out: list[dict[str, Any]] = []
        for row in chunks:
            content = str(getattr(row, "content", "") or "").strip()
            if not content:
                continue
            out.append(
                {
                    "chunk_id": str(getattr(row, "chunk_id", "")),
                    "content": content[:1200],
                    "similarity": round(float(getattr(row, "sim", 0.0)), 4),
                }
            )
        return out

    def retrieve_related_rules(
        self,
        prompt: str,
        user_id: UUID,
        top_k: int = 3,
        extraction: HybridExtractionResult | None = None,
    ) -> list[dict[str, Any]]:
        _ = user_id
        query = str(prompt or "").strip()
        if not query:
            return []
        try:
            return _build_rule_references(
                session=self.session,
                company_id=self.company_id,
                prompt=query,
                limit=max(1, min(int(top_k), 20)),
                extraction=extraction,
            )
        except Exception:
            return []


def _to_llm_style_rule_references(
    *,
    prompt: str,
    rule_references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prompt_families = _extract_target_families(prompt)
    out: list[dict[str, Any]] = []
    for ref in list(rule_references or []):
        name = str(ref.get("name") or "")
        description = str(ref.get("description") or "")
        ref_families = _extract_target_families(f"{name}\n{description}")
        if prompt_families and ref_families and not (prompt_families & ref_families):
            continue
        out.append(
            {
                "rule_id": str(ref.get("rule_id") or ""),
                "stable_key": str(ref.get("stable_key") or ""),
                "name": name,
                "scope": str(ref.get("scope") or ""),
                "action": str(ref.get("action") or ""),
                "severity": str(ref.get("severity") or ""),
                "priority": int(ref.get("priority") or 0),
                "match_mode": str(ref.get("match_mode") or "strict_keyword"),
                "origin": str(ref.get("origin") or ""),
                "prompt_overlap_score": float(ref.get("prompt_overlap_score") or 0.0),
            }
        )
    return out


def _generate_with_llm(
    prompt: str,
    *,
    extraction: HybridExtractionResult | None,
    prompt_keyword_bundle: PromptKeywordBundle,
    policy_chunks: list[dict[str, Any]],
    rule_references: list[dict[str, Any]],
    literal_detection: LiteralDetectionResult,
) -> tuple[RuleSuggestionDraftPayload, dict[str, Any]]:
    system_prompt = """
You generate security rule drafts in strict JSON.
Output ONLY one JSON object with this schema:
{
  "rule": {
    "stable_key": "string",
    "name": "string",
    "description": "string|null",
    "scope": "prompt|chat|file|api",
    "conditions": {"all":[{"signal":{"field":"persona","equals":"dev|office"}}]} OR {"any":[{"entity_type":"PHONE|CCCD|TAX_ID|EMAIL|CREDIT_CARD|API_SECRET|CUSTOM_SECRET"}]} OR {"all":[{"signal":{"field":"context_keywords","any_of":["<concrete_term_from_user_prompt>"]}}]},
    "action": "allow|mask|block",
    "severity": "low|medium|high",
    "priority": 0,
    "match_mode": "strict_keyword|keyword_plus_semantic",
    "rag_mode": "off|explain|verify",
    "enabled": true
  },
  "context_terms": [
    {
      "entity_type":"PHONE|CCCD|TAX_ID|PERSONA_*|INTERNAL_CODE|CUSTOM_SECRET",
      "term":"string",
      "lang":"vi|en",
      "weight":1.0,
      "window_1":60,
      "window_2":20,
      "enabled":true
    }
  ]
}
Return valid JSON only.
""".strip()

    target_phrases = _extraction_target_phrases(prompt, extraction=extraction, limit=8)
    if not target_phrases:
        target_phrases = _extract_meaningful_prompt_phrases(prompt, limit=8)
    helper_tokens = list((extraction or _empty_extraction()).helper_tokens or [])
    if not helper_tokens:
        helper_tokens = list(prompt_keyword_bundle.get("tokens") or [])
    business_phrases = _extraction_business_phrases(prompt, extraction=extraction, limit=8)
    context_modifiers = _svc()._unique_phrase_values(
        list((extraction or _empty_extraction()).context_modifiers)
    )[:8]
    prompt_context_phrases = _extraction_context_phrases(prompt, extraction=extraction, limit=8)
    llm_style_references = _to_llm_style_rule_references(
        prompt=prompt,
        rule_references=rule_references,
    )
    target_phrases_json = json.dumps(target_phrases, ensure_ascii=False)
    business_phrases_json = json.dumps(business_phrases, ensure_ascii=False)
    context_modifiers_json = json.dumps(context_modifiers, ensure_ascii=False)
    context_phrases_json = json.dumps(prompt_context_phrases, ensure_ascii=False)
    helper_tokens_json = json.dumps(helper_tokens[:24], ensure_ascii=False)
    policy_json = json.dumps(policy_chunks[:5], ensure_ascii=False)
    references_json = json.dumps(llm_style_references[:8], ensure_ascii=False)
    literal_detection_json = json.dumps(literal_detection.to_dict(), ensure_ascii=False)
    prompt_input = (
        "User request:\n"
        f"{prompt}\n\n"
        "Target phrases to preserve verbatim:\n"
        f"{target_phrases_json}\n\n"
        "Business phrases from structured extraction:\n"
        f"{business_phrases_json}\n\n"
        "Context modifiers from structured extraction:\n"
        f"{context_modifiers_json}\n\n"
        "Prompt context phrases (allowed for linked context terms only):\n"
        f"{context_phrases_json}\n\n"
        "Helper tokens for retrieval/context only (never emit as standalone condition keywords):\n"
        f"{helper_tokens_json}\n\n"
        "Literal identifier detection hint:\n"
        f"{literal_detection_json}\n\n"
        "Relevant policy excerpts:\n"
        f"{policy_json}\n\n"
        "Related existing rules (style-only, no keyword/context reuse):\n"
        f"{references_json}\n\n"
        "Task / output schema requirements:\n"
        "1) Prefer rule conditions consistent with existing rule DSL.\n"
        "2) stable_key must be personal-specific, never global.*.\n"
        "3) Use policy excerpts as grounding context when they are relevant.\n"
        "4) If related rule contains same policy intent, keep naming and conditions style close to that rule.\n"
        "5) Avoid generating redundant duplicate policy when related rules already cover it.\n"
        "6) If request mentions a specific internal code/token/secret that appears in the user request, prioritize exact-term protection and do not map to common PII entity types unless user explicitly asks.\n"
        "7) If request mentions payroll/salary plus personal/external email (e.g. gmail), draft conditions must reflect BOTH payroll domain and external-email risk, not generic office-only context.\n"
        "8) Respect literal identifier detection hint: INTERNAL_CODE means prefer deterministic exact-token protection; AMBIGUOUS means avoid forcing unrelated PII mapping.\n"
        "9) Preserve target phrase(s) from user request; only allow trim/whitespace/lowercase normalization, never semantic rewriting.\n"
        "10) Do not rewrite person-target phrases into company/school/organization-like labels.\n"
        "11) Related existing rules are style references only and must not override target phrase/entity from user request.\n"
        "12) For signal.field=context_keywords, use only meaningful phrase-level keywords from Target phrases.\n"
        "13) Do not output helper tokens as standalone context_keywords values.\n"
        "14) Do not copy linked context terms from related rules unless those terms are clearly grounded in the current user prompt.\n"
        "15) Never emit placeholder text such as 'literal refine required'.\n"
        "16) Never auto-fallback to conditions.entity_type=INTERNAL_CODE; when request is unclear, keep signal.field=context_keywords only.\n"
    )

    llm_out = generate_text_sync(
        prompt=prompt_input,
        system_prompt=system_prompt,
        provider=get_settings().non_embedding_llm_provider,
    )
    raw = llm_out.text
    obj = _svc()._parse_json_object(raw)
    return RuleSuggestionDraftPayload.model_validate(obj), {
        "source": "llm",
        "provider": str(llm_out.provider),
        "model": str(llm_out.model),
        "fallback_used": bool(llm_out.fallback_used),
    }


def _generate_draft_from_prompt(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    prompt: str,
) -> tuple[RuleSuggestionDraftPayload, dict[str, Any]]:
    normalized_prompt = _svc()._normalize_non_empty(value=prompt, field="prompt")
    extraction = _safe_extract_hybrid(normalized_prompt)
    literal_detection = _svc()._literal_detection(normalized_prompt, limit=8)
    prompt_keyword_bundle = _prompt_keyword_bundle_from_extraction(
        normalized_prompt,
        extraction=extraction,
        limit=16,
    )
    context_retriever = SuggestionContextRetriever(
        session=session,
        company_id=company_id,
    )
    policy_chunks = context_retriever.retrieve_policy_chunks(
        normalized_prompt,
        user_id=actor_user_id,
        top_k=3,
    )
    rule_references = context_retriever.retrieve_related_rules(
        normalized_prompt,
        user_id=actor_user_id,
        top_k=8,
        extraction=extraction,
    )
    policy_chunk_ids = _svc()._to_str_list([x.get("chunk_id") for x in policy_chunks])
    related_rule_ids = _svc()._to_str_list([x.get("rule_id") for x in rule_references])
    context_retrieval_meta = {
        "has_policy_context": bool(policy_chunk_ids),
        "policy_chunk_ids": policy_chunk_ids,
        "related_rule_ids": related_rule_ids,
        "policy_chunks": len(policy_chunks),
        "related_rules": len(rule_references),
    }

    try:
        draft, meta = _generate_with_llm(
            normalized_prompt,
            extraction=extraction,
            prompt_keyword_bundle=prompt_keyword_bundle,
            policy_chunks=policy_chunks,
            rule_references=rule_references,
            literal_detection=literal_detection,
        )
        meta["context_retrieval"] = context_retrieval_meta
        meta["literal_detection"] = literal_detection.to_dict()
    except Exception:
        try:
            draft = _fallback_generate(normalized_prompt, extraction=extraction)
            meta = {
                "source": "fallback_generator",
                "provider": "none",
                "model": "none",
                "fallback_used": False,
                "context_retrieval": context_retrieval_meta,
                "literal_detection": literal_detection.to_dict(),
            }
        except Exception:
            draft = _build_minimal_safe_prompt_draft(
                prompt=normalized_prompt,
                extraction=extraction,
            )
            meta = {
                "source": "safe_minimal_fallback_after_generation_error",
                "provider": "none",
                "model": "none",
                "fallback_used": False,
                "context_retrieval": context_retrieval_meta,
                "literal_detection": literal_detection.to_dict(),
            }

    draft = _svc()._sanitize_debug_placeholder_text(prompt=normalized_prompt, draft=draft)
    draft = _svc()._realign_literal_specific_draft(prompt=normalized_prompt, draft=draft)
    draft = _svc()._align_draft_with_prompt(normalized_prompt, draft)
    draft = _svc()._enforce_prompt_semantic_guard(normalized_prompt, draft)
    draft, intent_guard_meta = _svc()._post_generate_intent_guard(
        prompt=normalized_prompt,
        draft=draft,
    )
    draft, runtime_usability_meta = _svc()._apply_runtime_usability_constraint(
        prompt=normalized_prompt,
        draft=draft,
    )
    draft = _svc()._realign_literal_specific_draft(prompt=normalized_prompt, draft=draft)
    draft = _svc()._sanitize_draft_context_keywords(
        draft=draft,
        prompt_keyword_bundle=prompt_keyword_bundle,
    )
    draft = _svc()._filter_and_ground_context_terms(
        prompt=normalized_prompt,
        draft=draft,
        prompt_keyword_bundle=prompt_keyword_bundle,
    )
    draft, keyword_context_contract_meta = _svc()._enforce_keyword_context_role_contract(
        prompt=normalized_prompt,
        draft=draft,
        prompt_keyword_bundle=prompt_keyword_bundle,
    )
    draft = _svc()._sanitize_debug_placeholder_text(prompt=normalized_prompt, draft=draft)
    meta["intent_guard"] = intent_guard_meta
    meta["runtime_usability"] = runtime_usability_meta
    meta["keyword_context_contract"] = keyword_context_contract_meta
    try:
        normalized = _svc()._normalize_draft(draft)
        normalized = _svc()._sanitize_debug_placeholder_text(prompt=normalized_prompt, draft=normalized)
        return _svc()._normalize_draft(normalized), meta
    except Exception:
        safe = _build_minimal_safe_prompt_draft(
            prompt=normalized_prompt,
            extraction=extraction,
        )
        safe = _svc()._sanitize_debug_placeholder_text(prompt=normalized_prompt, draft=safe)
        return _svc()._normalize_draft(safe), {
            "source": "safe_minimal_fallback_after_processing_error",
            "provider": "none",
            "model": "none",
            "fallback_used": False,
            "context_retrieval": context_retrieval_meta,
            "literal_detection": literal_detection.to_dict(),
            "intent_guard": {"applied": False, "mismatch_detected": False, "reasons": ["safe_minimal_fallback"]},
            "runtime_usability": {
                "runtime_usable": True,
                "warnings": [],
                "repair_applied": True,
                "reasons": ["safe_minimal_fallback"],
                "abstract_terms": [],
            },
            "keyword_context_contract": {"applied": True, "reason": "safe_minimal_fallback"},
        }
