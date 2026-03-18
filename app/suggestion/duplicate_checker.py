from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.core.config import get_settings
from app.llm import generate_text_sync
from app.rule.model import Rule
from app.rule_embedding.model import RuleEmbedding
from app.suggestion.schemas import (
    DuplicateDecision,
    RuleDuplicateCandidateOut,
    RuleDuplicateCheckOut,
    RuleSuggestionDraftRule,
)


EMBED_DIM = 1536
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _Candidate:
    rule_id: UUID
    stable_key: str
    name: str
    origin: str
    similarity: float
    lexical_score: float
    hybrid_score: float
    signature_hash: str
    semantic_hash: str
    scope: str
    action: str
    severity: str
    rag_mode: str
    priority: int
    conditions: dict[str, Any]


@dataclass(slots=True)
class _LlmMeta:
    provider: str
    model: str
    fallback_used: bool


def _normalize_conditions(conditions: dict[str, Any]) -> str:
    return json.dumps(conditions, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _rule_signature_hash(
    *,
    stable_key: str,
    scope: str,
    action: str,
    severity: str,
    rag_mode: str,
    conditions: dict[str, Any],
) -> str:
    raw = json.dumps(
        {
            "stable_key": stable_key.strip().lower(),
            "scope": scope,
            "action": action,
            "severity": severity,
            "rag_mode": rag_mode,
            "conditions": json.loads(_normalize_conditions(conditions)),
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rule_semantic_hash(
    *,
    scope: str,
    action: str,
    severity: str,
    rag_mode: str,
    priority: int,
    conditions: dict[str, Any],
) -> str:
    raw = json.dumps(
        {
            "scope": scope,
            "action": action,
            "severity": severity,
            "rag_mode": rag_mode,
            "priority": int(priority),
            "conditions": json.loads(_normalize_conditions(conditions)),
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rule_to_text(
    *,
    stable_key: str,
    name: str,
    description: str | None,
    scope: str,
    action: str,
    severity: str,
    rag_mode: str,
    priority: int,
    conditions: dict[str, Any],
) -> str:
    return "\n".join(
        [
            f"stable_key: {stable_key}",
            f"name: {name}",
            f"description: {description or ''}",
            f"scope: {scope}",
            f"action: {action}",
            f"severity: {severity}",
            f"rag_mode: {rag_mode}",
            f"priority: {int(priority)}",
            f"conditions: {_normalize_conditions(conditions)}",
        ]
    )


def draft_rule_to_text(draft: RuleSuggestionDraftRule) -> str:
    return _rule_to_text(
        stable_key=draft.stable_key,
        name=draft.name,
        description=draft.description,
        scope=draft.scope.value,
        action=draft.action.value,
        severity=draft.severity.value,
        rag_mode=draft.rag_mode.value,
        priority=draft.priority,
        conditions=draft.conditions,
    )


def _tokenize(text: str) -> set[str]:
    parts = re.split(r"[^a-zA-Z0-9_]+", (text or "").lower())
    return {p for p in parts if p}


def _lexical_score(a: str, b: str) -> float:
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    if union == 0:
        return 0.0
    return float(inter / union)


def _hash_embedding(text: str) -> list[float]:
    vec = [0.0] * EMBED_DIM
    tokens = sorted(_tokenize(text))
    if not tokens:
        return vec

    for token in tokens:
        h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        idx = h % EMBED_DIM
        sign = -1.0 if ((h >> 1) & 1) else 1.0
        weight = 1.0 + ((h % 100) / 500.0)
        vec[idx] += sign * weight

    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 0:
        return vec
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return float(sum(a[i] * b[i] for i in range(n)))


def _hybrid_score(*, similarity: float, lexical_score: float) -> float:
    # Weighted score to reduce false negatives when one signal is weak.
    return (0.78 * float(similarity)) + (0.22 * float(lexical_score))


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _extract_entity_types(node: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(node, dict):
        if "entity_type" in node:
            value = str(node.get("entity_type") or "").strip().upper()
            if value:
                out.add(value)
        for v in node.values():
            out.update(_extract_entity_types(v))
        return out
    if isinstance(node, list):
        for item in node:
            out.update(_extract_entity_types(item))
    return out


def _extract_signal_fields(node: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(node, dict):
        signal = node.get("signal")
        if isinstance(signal, dict):
            field = str(signal.get("field") or "").strip().lower()
            if field:
                out.add(field)
        for v in node.values():
            out.update(_extract_signal_fields(v))
        return out
    if isinstance(node, list):
        for item in node:
            out.update(_extract_signal_fields(item))
    return out


def _top_signal_family(fields: set[str]) -> str:
    if "persona" in fields:
        return "persona"
    if "rag" in fields:
        return "rag"
    if "security" in fields:
        return "security"
    if "risk_boost" in fields:
        return "risk"
    if fields:
        return sorted(fields)[0]
    return ""


def _is_candidate_intent_compatible(
    *,
    draft_rule: RuleSuggestionDraftRule,
    candidate: _Candidate,
) -> bool:
    if str(candidate.scope) != str(draft_rule.scope.value):
        return False
    if str(candidate.action) != str(draft_rule.action.value):
        return False

    draft_entities = _extract_entity_types(draft_rule.conditions)
    cand_entities = _extract_entity_types(candidate.conditions)
    if draft_entities:
        if not cand_entities:
            return False
        if not (draft_entities & cand_entities):
            return False
    elif cand_entities:
        return False

    draft_signals = _extract_signal_fields(draft_rule.conditions)
    cand_signals = _extract_signal_fields(candidate.conditions)
    if draft_signals:
        if not cand_signals:
            return False
        draft_family = _top_signal_family(draft_signals)
        cand_family = _top_signal_family(cand_signals)
        if draft_family and cand_family and draft_family != cand_family:
            return False
    elif cand_signals:
        return False

    return True


def _structural_similarity(
    *,
    draft_rule: RuleSuggestionDraftRule,
    candidate: _Candidate,
) -> float:
    score = 0.0
    if candidate.scope == draft_rule.scope.value:
        score += 0.25
    if candidate.action == draft_rule.action.value:
        score += 0.25
    if candidate.rag_mode == draft_rule.rag_mode.value:
        score += 0.10
    if candidate.severity == draft_rule.severity.value:
        score += 0.10

    draft_entities = _extract_entity_types(draft_rule.conditions)
    cand_entities = _extract_entity_types(candidate.conditions)
    if draft_entities and cand_entities:
        inter = len(draft_entities & cand_entities)
        union = len(draft_entities | cand_entities)
        if union > 0:
            score += 0.30 * (inter / union)
    return _clamp01(score)


def _adjust_hybrid_score(
    *,
    base_hybrid: float,
    structural_score: float,
    draft_rule: RuleSuggestionDraftRule,
    rule: Rule,
) -> float:
    adjusted = float(base_hybrid)
    adjusted += 0.18 * structural_score

    draft_entities = _extract_entity_types(draft_rule.conditions)
    rule_entities = _extract_entity_types(rule.conditions)
    if draft_entities and rule_entities:
        if draft_entities & rule_entities:
            adjusted += 0.06
        else:
            adjusted -= 0.14

    if str(rule.action.value) != str(draft_rule.action.value):
        adjusted -= 0.05

    if (
        str(rule.stable_key).startswith("global.security.rag.")
        and len(_extract_entity_types(draft_rule.conditions)) > 0
    ):
        adjusted -= 0.08

    if rule.company_id is not None:
        adjusted += 0.03

    return _clamp01(adjusted)


def _should_call_llm_for_duplicate(
    *,
    draft_rule: RuleSuggestionDraftRule,
    candidates: list[_Candidate],
    near_threshold: float,
) -> bool:
    if not candidates:
        return False
    best = candidates[0]
    structural = _structural_similarity(draft_rule=draft_rule, candidate=best)

    if best.hybrid_score >= max(0.78, near_threshold * 0.95):
        return True
    if structural >= 0.72 and best.hybrid_score >= 0.60:
        return True
    if best.similarity >= max(0.78, near_threshold * 0.97) and best.lexical_score >= 0.55:
        return True
    return False


def _to_candidate_out(c: _Candidate) -> RuleDuplicateCandidateOut:
    return RuleDuplicateCandidateOut(
        rule_id=c.rule_id,
        stable_key=c.stable_key,
        name=c.name,
        origin=c.origin,
        similarity=float(c.similarity),
        lexical_score=float(c.lexical_score),
    )


def _is_similar_rule_candidate(*, candidate: _Candidate, near_threshold: float) -> bool:
    return bool(
        candidate.similarity >= near_threshold
        or candidate.hybrid_score >= near_threshold
        or candidate.lexical_score >= 0.78
    )


def _candidate_log_row(candidate: _Candidate) -> dict[str, Any]:
    return {
        "rule_id": str(candidate.rule_id),
        "stable_key": candidate.stable_key,
        "origin": candidate.origin,
        "similarity": round(float(candidate.similarity), 6),
        "lexical_score": round(float(candidate.lexical_score), 6),
        "hybrid_score": round(float(candidate.hybrid_score), 6),
    }


def _ensure_rule_embedding(
    *,
    session: Session,
    rule: Rule,
    model_name: str,
) -> list[float]:
    text = _rule_to_text(
        stable_key=rule.stable_key,
        name=rule.name,
        description=rule.description,
        scope=rule.scope.value,
        action=rule.action.value,
        severity=rule.severity.value,
        rag_mode=rule.rag_mode.value,
        priority=rule.priority,
        conditions=rule.conditions,
    )
    content_hash = hashlib.sha256(f"{rule.id}:{text}".encode("utf-8")).hexdigest()
    emb = _hash_embedding(text)

    row = session.exec(
        select(RuleEmbedding)
        .where(RuleEmbedding.rule_id == rule.id)
        .where(RuleEmbedding.model_name == model_name)
    ).first()

    if row is None:
        row = RuleEmbedding(
            rule_id=rule.id,
            content=text,
            content_hash=content_hash,
            embedding=emb,
            model_name=model_name,
        )
    else:
        row.content = text
        row.content_hash = content_hash
        row.embedding = emb

    session.add(row)
    session.flush()
    return emb


def _llm_classify_duplicate(
    *,
    draft_rule: RuleSuggestionDraftRule,
    candidates: list[_Candidate],
    exact_threshold: float,
    near_threshold: float,
) -> tuple[DuplicateDecision, list[UUID], float, str, _LlmMeta]:
    if not candidates:
        return (
            DuplicateDecision.different,
            [],
            0.0,
            "no_candidates",
            _LlmMeta(provider="none", model="none", fallback_used=False),
        )
    settings = get_settings()

    candidate_payload = [
        {
            "rule_id": str(c.rule_id),
            "stable_key": c.stable_key,
            "name": c.name,
            "origin": c.origin,
            "similarity": round(c.similarity, 6),
            "lexical_score": round(c.lexical_score, 6),
            "hybrid_score": round(c.hybrid_score, 6),
            "scope": c.scope,
            "action": c.action,
            "severity": c.severity,
            "rag_mode": c.rag_mode,
            "priority": int(c.priority),
            "conditions": c.conditions,
        }
        for c in candidates
    ]

    prompt = (
        "You are a strict duplicate-rule classifier.\n"
        "Classify draft rule against candidates and output ONLY JSON.\n"
        "decision must be EXACT_DUPLICATE or NEAR_DUPLICATE or DIFFERENT.\n"
        "EXACT_DUPLICATE only when policy intent and execution behavior are effectively the same.\n"
        "Schema: {\"decision\":str,\"matched_rule_ids\":[str],\"confidence\":0..1,\"rationale\":str}\n\n"
        f"Thresholds: exact={float(exact_threshold):.3f}, near={float(near_threshold):.3f}\n\n"
        f"Draft rule:\n{json.dumps(draft_rule.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        f"Candidates:\n{json.dumps(candidate_payload, ensure_ascii=False)}\n"
    )

    llm_out = generate_text_sync(
        prompt=prompt,
        provider=settings.non_embedding_llm_provider,
        timeout_s=settings.non_embedding_llm_timeout_seconds,
    )
    raw = llm_out.text

    try:
        parsed = json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(raw[start : end + 1])

    decision_raw = str(parsed.get("decision") or "").strip().upper()
    if decision_raw not in {"EXACT_DUPLICATE", "NEAR_DUPLICATE", "DIFFERENT"}:
        decision_raw = "DIFFERENT"

    matched_ids: list[UUID] = []
    for x in list(parsed.get("matched_rule_ids") or []):
        try:
            matched_ids.append(UUID(str(x)))
        except Exception:
            continue

    confidence = float(parsed.get("confidence") or 0.5)
    confidence = max(0.0, min(1.0, confidence))
    rationale = str(parsed.get("rationale") or "").strip()[:1000] or "llm_result"

    return (
        DuplicateDecision(decision_raw),
        matched_ids,
        confidence,
        rationale,
        _LlmMeta(
            provider=str(llm_out.provider),
            model=str(llm_out.model),
            fallback_used=bool(llm_out.fallback_used),
        ),
    )


def _fallback_decision(
    *,
    draft_rule: RuleSuggestionDraftRule,
    candidates: list[_Candidate],
    exact_threshold: float,
    near_threshold: float,
) -> tuple[DuplicateDecision, list[UUID], float, str]:
    if not candidates:
        return DuplicateDecision.different, [], 0.0, "no_candidates"

    best = candidates[0]
    if (best.similarity >= exact_threshold) or (
        best.hybrid_score >= exact_threshold and best.lexical_score >= 0.65
    ):
        return (
            DuplicateDecision.exact_duplicate,
            [best.rule_id],
            min(1.0, max(best.similarity, best.hybrid_score)),
            "hybrid_above_exact_threshold",
        )
    if (
        best.similarity >= near_threshold
        or best.hybrid_score >= near_threshold
        or best.lexical_score >= 0.78
    ):
        return (
            DuplicateDecision.near_duplicate,
            [best.rule_id],
            min(1.0, max(best.similarity, best.hybrid_score)),
            "hybrid_above_near_threshold",
        )

    structural = _structural_similarity(draft_rule=draft_rule, candidate=best)
    if structural >= 0.72 and best.hybrid_score >= 0.58:
        return (
            DuplicateDecision.near_duplicate,
            [best.rule_id],
            _clamp01((best.hybrid_score + structural) / 2.0),
            "structural_near_duplicate",
        )
    return (
        DuplicateDecision.different,
        [],
        max(0.0, 1.0 - max(best.similarity, best.hybrid_score)),
        "below_threshold",
    )


def build_duplicate_check(
    *,
    session: Session,
    company_id: UUID,
    draft_rule: RuleSuggestionDraftRule,
) -> RuleDuplicateCheckOut:
    settings = get_settings()
    top_k = max(1, int(settings.rule_duplicate_top_k))
    exact_th = float(settings.rule_duplicate_exact_threshold)
    near_th = float(settings.rule_duplicate_near_threshold)
    model_name = settings.rule_duplicate_embed_model

    draft_text = draft_rule_to_text(draft_rule)
    draft_emb = _hash_embedding(draft_text)
    draft_sig = _rule_signature_hash(
        stable_key=draft_rule.stable_key,
        scope=draft_rule.scope.value,
        action=draft_rule.action.value,
        severity=draft_rule.severity.value,
        rag_mode=draft_rule.rag_mode.value,
        conditions=draft_rule.conditions,
    )
    draft_semantic = _rule_semantic_hash(
        scope=draft_rule.scope.value,
        action=draft_rule.action.value,
        severity=draft_rule.severity.value,
        rag_mode=draft_rule.rag_mode.value,
        priority=int(draft_rule.priority),
        conditions=draft_rule.conditions,
    )

    rows = list(
        session.exec(
            select(Rule).where(
                (Rule.company_id.is_(None)) | (Rule.company_id == company_id)
            )
        ).all()
    )

    scored: list[_Candidate] = []
    for r in rows:
        emb = _ensure_rule_embedding(session=session, rule=r, model_name=model_name)
        text = _rule_to_text(
            stable_key=r.stable_key,
            name=r.name,
            description=r.description,
            scope=r.scope.value,
            action=r.action.value,
            severity=r.severity.value,
            rag_mode=r.rag_mode.value,
            priority=r.priority,
            conditions=r.conditions,
        )
        sim = _cosine(draft_emb, list(emb))
        lex = _lexical_score(draft_text, text)
        sig = _rule_signature_hash(
            stable_key=r.stable_key,
            scope=r.scope.value,
            action=r.action.value,
            severity=r.severity.value,
            rag_mode=r.rag_mode.value,
            conditions=r.conditions,
        )
        semantic = _rule_semantic_hash(
            scope=r.scope.value,
            action=r.action.value,
            severity=r.severity.value,
            rag_mode=r.rag_mode.value,
            priority=int(r.priority),
            conditions=r.conditions,
        )
        hybrid = _hybrid_score(similarity=sim, lexical_score=lex)
        structural = _structural_similarity(draft_rule=draft_rule, candidate=_Candidate(
            rule_id=r.id,
            stable_key=r.stable_key,
            name=r.name,
            origin="global_default" if r.company_id is None else "personal_rule",
            similarity=sim,
            lexical_score=lex,
            hybrid_score=hybrid,
            signature_hash=sig,
            semantic_hash=semantic,
            scope=r.scope.value,
            action=r.action.value,
            severity=r.severity.value,
            rag_mode=r.rag_mode.value,
            priority=int(r.priority),
            conditions=r.conditions,
        ))
        hybrid = _adjust_hybrid_score(
            base_hybrid=hybrid,
            structural_score=structural,
            draft_rule=draft_rule,
            rule=r,
        )
        scored.append(
            _Candidate(
                rule_id=r.id,
                stable_key=r.stable_key,
                name=r.name,
                origin="global_default" if r.company_id is None else "personal_rule",
                similarity=sim,
                lexical_score=lex,
                hybrid_score=hybrid,
                signature_hash=sig,
                semantic_hash=semantic,
                scope=r.scope.value,
                action=r.action.value,
                severity=r.severity.value,
                rag_mode=r.rag_mode.value,
                priority=int(r.priority),
                conditions=r.conditions,
            )
        )

    scored.sort(
        key=lambda x: (x.hybrid_score, x.similarity, x.lexical_score),
        reverse=True,
    )
    ranked_top = scored[:top_k]
    compatible = [
        c
        for c in scored
        if _is_candidate_intent_compatible(draft_rule=draft_rule, candidate=c)
    ]
    ranking_pool = compatible
    top = ranking_pool[:top_k]
    similar_candidates = [
        c
        for c in ranking_pool
        if _is_similar_rule_candidate(candidate=c, near_threshold=near_th)
    ][:top_k]

    logger.debug(
        "duplicate_check_scoring draft_key=%s top_k=%d thresholds={exact:%.3f,near:%.3f} "
        "candidate_counts={all:%d,compatible:%d,similar:%d} ranked_top=%s compatible_top=%s similar_top=%s",
        draft_rule.stable_key,
        top_k,
        exact_th,
        near_th,
        len(scored),
        len(compatible),
        len(similar_candidates),
        json.dumps([_candidate_log_row(c) for c in ranked_top], ensure_ascii=False),
        json.dumps([_candidate_log_row(c) for c in top], ensure_ascii=False),
        json.dumps([_candidate_log_row(c) for c in similar_candidates], ensure_ascii=False),
    )

    # Hard deterministic checks first, evaluated on full candidate set.
    same_key = [c for c in scored if c.stable_key == draft_rule.stable_key]
    if same_key:
        c = same_key[0]
        logger.debug(
            "duplicate_check_deterministic draft_key=%s reason=stable_key_conflict matched_rule_id=%s",
            draft_rule.stable_key,
            str(c.rule_id),
        )
        return RuleDuplicateCheckOut(
            decision=DuplicateDecision.exact_duplicate,
            confidence=1.0,
            rationale="stable_key_conflict",
            matched_rule_ids=[c.rule_id],
            candidates=[_to_candidate_out(x) for x in similar_candidates],
            top_k=top_k,
            exact_threshold=exact_th,
            near_threshold=near_th,
            source="hard_deterministic",
        )

    same_sig = [c for c in scored if c.signature_hash == draft_sig]
    if same_sig:
        c = same_sig[0]
        logger.debug(
            "duplicate_check_deterministic draft_key=%s reason=normalized_signature_match matched_rule_id=%s",
            draft_rule.stable_key,
            str(c.rule_id),
        )
        return RuleDuplicateCheckOut(
            decision=DuplicateDecision.exact_duplicate,
            confidence=1.0,
            rationale="normalized_signature_match",
            matched_rule_ids=[c.rule_id],
            candidates=[_to_candidate_out(x) for x in similar_candidates],
            top_k=top_k,
            exact_threshold=exact_th,
            near_threshold=near_th,
            source="hard_deterministic",
        )

    same_semantic = [c for c in scored if c.semantic_hash == draft_semantic]
    if same_semantic:
        c = same_semantic[0]
        logger.debug(
            "duplicate_check_deterministic draft_key=%s reason=semantic_signature_match matched_rule_id=%s",
            draft_rule.stable_key,
            str(c.rule_id),
        )
        return RuleDuplicateCheckOut(
            decision=DuplicateDecision.exact_duplicate,
            confidence=min(1.0, max(c.similarity, c.hybrid_score)),
            rationale="semantic_signature_match",
            matched_rule_ids=[c.rule_id],
            candidates=[_to_candidate_out(x) for x in similar_candidates],
            top_k=top_k,
            exact_threshold=exact_th,
            near_threshold=near_th,
            source="hard_deterministic",
        )

    if _should_call_llm_for_duplicate(
        draft_rule=draft_rule,
        candidates=top,
        near_threshold=near_th,
    ):
        try:
            decision, matched_ids, conf, rationale, llm_meta = _llm_classify_duplicate(
                draft_rule=draft_rule,
                candidates=top,
                exact_threshold=exact_th,
                near_threshold=near_th,
            )
            source = "llm"
        except Exception:
            decision, matched_ids, conf, rationale = _fallback_decision(
                draft_rule=draft_rule,
                candidates=top,
                exact_threshold=exact_th,
                near_threshold=near_th,
            )
            llm_meta = _LlmMeta(provider="none", model="none", fallback_used=False)
            source = "fallback_similarity"
    else:
        decision, matched_ids, conf, rationale = _fallback_decision(
            draft_rule=draft_rule,
            candidates=top,
            exact_threshold=exact_th,
            near_threshold=near_th,
        )
        llm_meta = _LlmMeta(provider="none", model="none", fallback_used=False)
        source = "hybrid_fastpath"

    top_ids = {x.rule_id for x in top}
    matched_ids = [x for x in matched_ids if x in top_ids]
    if decision != DuplicateDecision.different and not matched_ids and top:
        matched_ids = [top[0].rule_id]

    logger.debug(
        "duplicate_check_final draft_key=%s source=%s decision=%s confidence=%.4f rationale=%s matched_rule_ids=%s similar_rules=%s",
        draft_rule.stable_key,
        source,
        decision.value,
        float(conf),
        rationale,
        json.dumps([str(x) for x in matched_ids]),
        json.dumps([_candidate_log_row(c) for c in similar_candidates], ensure_ascii=False),
    )

    return RuleDuplicateCheckOut(
        decision=decision,
        confidence=conf,
        rationale=rationale,
        matched_rule_ids=matched_ids,
        candidates=[_to_candidate_out(x) for x in similar_candidates],
        top_k=top_k,
        exact_threshold=exact_th,
        near_threshold=near_th,
        source=source,
        llm_provider=llm_meta.provider if source == "llm" else None,
        llm_model=llm_meta.model if source == "llm" else None,
        llm_fallback_used=bool(llm_meta.fallback_used) if source == "llm" else False,
    )
