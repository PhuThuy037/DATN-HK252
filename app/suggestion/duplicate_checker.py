from __future__ import annotations

import hashlib
import json
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


@dataclass(slots=True)
class _Candidate:
    rule_id: UUID
    stable_key: str
    name: str
    origin: str
    similarity: float
    lexical_score: float
    signature_hash: str


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
) -> tuple[DuplicateDecision, list[UUID], float, str]:
    if not candidates:
        return DuplicateDecision.different, [], 0.0, "no_candidates"
    settings = get_settings()

    candidate_payload = [
        {
            "rule_id": str(c.rule_id),
            "stable_key": c.stable_key,
            "name": c.name,
            "origin": c.origin,
            "similarity": round(c.similarity, 6),
            "lexical_score": round(c.lexical_score, 6),
        }
        for c in candidates
    ]

    prompt = (
        "You are a strict duplicate-rule classifier.\n"
        "Classify draft rule against candidates and output ONLY JSON.\n"
        "decision must be EXACT_DUPLICATE or NEAR_DUPLICATE or DIFFERENT.\n"
        "Schema: {\"decision\":str,\"matched_rule_ids\":[str],\"confidence\":0..1,\"rationale\":str}\n\n"
        f"Draft rule:\n{json.dumps(draft_rule.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        f"Candidates:\n{json.dumps(candidate_payload, ensure_ascii=False)}\n"
    )

    raw = generate_text_sync(
        prompt=prompt,
        provider=settings.non_embedding_llm_provider,
        timeout_s=settings.non_embedding_llm_timeout_seconds,
    ).text

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

    return DuplicateDecision(decision_raw), matched_ids, confidence, rationale


def _fallback_decision(
    *,
    candidates: list[_Candidate],
    exact_threshold: float,
    near_threshold: float,
) -> tuple[DuplicateDecision, list[UUID], float, str]:
    if not candidates:
        return DuplicateDecision.different, [], 0.0, "no_candidates"

    best = candidates[0]
    if best.similarity >= exact_threshold:
        return (
            DuplicateDecision.exact_duplicate,
            [best.rule_id],
            min(1.0, best.similarity),
            "similarity_above_exact_threshold",
        )
    if best.similarity >= near_threshold:
        return (
            DuplicateDecision.near_duplicate,
            [best.rule_id],
            min(1.0, best.similarity),
            "similarity_above_near_threshold",
        )
    return DuplicateDecision.different, [], 1.0 - best.similarity, "below_threshold"


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
        scored.append(
            _Candidate(
                rule_id=r.id,
                stable_key=r.stable_key,
                name=r.name,
                origin="global_default" if r.company_id is None else "company_rule",
                similarity=sim,
                lexical_score=lex,
                signature_hash=sig,
            )
        )

    scored.sort(key=lambda x: (x.similarity, x.lexical_score), reverse=True)
    top = scored[:top_k]

    # Hard deterministic checks first.
    same_key = [c for c in top if c.stable_key == draft_rule.stable_key]
    if same_key:
        c = same_key[0]
        return RuleDuplicateCheckOut(
            decision=DuplicateDecision.exact_duplicate,
            confidence=1.0,
            rationale="stable_key_conflict",
            matched_rule_ids=[c.rule_id],
            candidates=[
                RuleDuplicateCandidateOut(
                    rule_id=x.rule_id,
                    stable_key=x.stable_key,
                    name=x.name,
                    origin=x.origin,
                    similarity=float(x.similarity),
                    lexical_score=float(x.lexical_score),
                )
                for x in top
            ],
            top_k=top_k,
            exact_threshold=exact_th,
            near_threshold=near_th,
            source="hard_deterministic",
        )

    same_sig = [c for c in top if c.signature_hash == draft_sig]
    if same_sig:
        c = same_sig[0]
        return RuleDuplicateCheckOut(
            decision=DuplicateDecision.exact_duplicate,
            confidence=1.0,
            rationale="normalized_signature_match",
            matched_rule_ids=[c.rule_id],
            candidates=[
                RuleDuplicateCandidateOut(
                    rule_id=x.rule_id,
                    stable_key=x.stable_key,
                    name=x.name,
                    origin=x.origin,
                    similarity=float(x.similarity),
                    lexical_score=float(x.lexical_score),
                )
                for x in top
            ],
            top_k=top_k,
            exact_threshold=exact_th,
            near_threshold=near_th,
            source="hard_deterministic",
        )

    try:
        decision, matched_ids, conf, rationale = _llm_classify_duplicate(
            draft_rule=draft_rule,
            candidates=top,
        )
        source = "llm"
    except Exception:
        decision, matched_ids, conf, rationale = _fallback_decision(
            candidates=top,
            exact_threshold=exact_th,
            near_threshold=near_th,
        )
        source = "fallback_similarity"

    return RuleDuplicateCheckOut(
        decision=decision,
        confidence=conf,
        rationale=rationale,
        matched_rule_ids=matched_ids,
        candidates=[
            RuleDuplicateCandidateOut(
                rule_id=x.rule_id,
                stable_key=x.stable_key,
                name=x.name,
                origin=x.origin,
                similarity=float(x.similarity),
                lexical_score=float(x.lexical_score),
            )
            for x in top
        ],
        top_k=top_k,
        exact_threshold=exact_th,
        near_threshold=near_th,
        source=source,
    )
