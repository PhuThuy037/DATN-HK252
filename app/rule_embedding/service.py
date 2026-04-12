from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.common.enums import MatchMode, RagMode, RuleAction, RuleScope
from app.core.config import get_settings
from app.rag.models.context_term import ContextTerm
from app.rule.engine import RuleEngine
from app.rule.model import Rule
from app.rule.rule_context_term_link import RuleContextTermLink
from app.rule_embedding.model import RuleEmbedding


EMBED_DIM = 1536
_RAG_RULE_KEY_PREFIX = "global.security.rag."
_SEMANTIC_ASSIST_MIN_CONFIDENCE = 0.28
_SEMANTIC_ASSIST_MAX_SUPPORTED = 5


@dataclass(slots=True, frozen=True)
class SemanticAssistScore:
    stable_key: str
    confidence: float
    priority: int


@dataclass(slots=True, frozen=True)
class SemanticVerifyMaterial:
    rule_id: UUID
    stable_key: str
    name: str
    description: str
    conditions: dict[str, Any]
    conditions_summary: str
    linked_context_terms: list[str]
    target_phrases: list[str]
    topic_phrases: list[str]
    target_evidence: list[str]
    topic_evidence: list[str]


def _normalize_conditions(conditions: dict[str, Any]) -> str:
    return json.dumps(conditions, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def build_rule_embedding_content(rule: Rule) -> str:
    return "\n".join(
        [
            f"stable_key: {rule.stable_key}",
            f"name: {rule.name}",
            f"description: {rule.description or ''}",
            f"scope: {rule.scope.value}",
            f"action: {rule.action.value}",
            f"severity: {rule.severity.value}",
            f"rag_mode: {rule.rag_mode.value}",
            f"priority: {int(rule.priority)}",
            f"conditions: {_normalize_conditions(rule.conditions)}",
        ]
    )


def build_semantic_assist_rule_content(
    *,
    rule: Rule,
    context_terms: Sequence[ContextTerm],
) -> str:
    linked_terms = [
        {
            "entity_type": str(row.entity_type or "").strip().upper(),
            "term": str(row.term or "").strip().lower(),
            "lang": str(row.lang or "").strip().lower(),
        }
        for row in sorted(
            list(context_terms or []),
            key=lambda item: (
                str(getattr(item, "entity_type", "") or "").upper(),
                str(getattr(item, "term", "") or "").lower(),
                str(getattr(item, "lang", "") or "").lower(),
            ),
        )
        if str(getattr(row, "term", "") or "").strip()
    ]
    linked_term_lines = [
        str(row.get("term") or "").strip()
        for row in linked_terms
        if str(row.get("term") or "").strip()
    ]
    return "\n".join(
        [
            f"name: {rule.name}",
            f"description: {rule.description or ''}",
            f"conditions: {_normalize_conditions(rule.conditions or {})}",
            f"conditions_summary: {summarize_rule_conditions(rule.conditions or {})}",
            "linked_context_term_lines: " + " | ".join(linked_term_lines),
            "linked_context_terms: "
            + json.dumps(linked_terms, ensure_ascii=False, separators=(",", ":")),
        ]
    )


def hash_rule_embedding_content(text: str) -> list[float]:
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


def upsert_rule_embedding(
    *,
    session: Session,
    rule: Rule,
    model_name: str | None = None,
) -> list[float]:
    resolved_model = str(model_name or get_settings().rule_duplicate_embed_model)
    text = build_rule_embedding_content(rule)
    content_hash = hashlib.sha256(f"{rule.id}:{text}".encode("utf-8")).hexdigest()
    emb = hash_rule_embedding_content(text)

    row = session.exec(
        select(RuleEmbedding)
        .where(RuleEmbedding.rule_id == rule.id)
        .where(RuleEmbedding.model_name == resolved_model)
    ).first()

    if row is None:
        row = RuleEmbedding(
            rule_id=rule.id,
            content=text,
            content_hash=content_hash,
            embedding=emb,
            model_name=resolved_model,
        )
    else:
        row.content = text
        row.content_hash = content_hash
        row.embedding = emb

    session.add(row)
    session.flush()
    return emb


def backfill_rule_embeddings(
    *,
    session: Session,
    rules: Sequence[Rule],
    model_name: str | None = None,
) -> int:
    total = 0
    for rule in rules:
        upsert_rule_embedding(session=session, rule=rule, model_name=model_name)
        total += 1
    return total


def summarize_rule_conditions(conditions: dict[str, Any]) -> str:
    def _render(node: Any) -> str:
        if isinstance(node, dict):
            if "all" in node:
                parts = [_render(item) for item in (node.get("all") or [])]
                parts = [part for part in parts if part]
                return " AND ".join(parts)

            if "any" in node:
                parts = [_render(item) for item in (node.get("any") or [])]
                parts = [part for part in parts if part]
                return " OR ".join(parts)

            if "not" in node:
                inner = _render(node.get("not"))
                return f"NOT ({inner})" if inner else ""

            if "entity_type" in node:
                entity_type = str(node.get("entity_type") or "").strip()
                min_score = node.get("min_score")
                if min_score is None:
                    return f"entity:{entity_type}"
                return f"entity:{entity_type} score>={min_score}"

            signal = node.get("signal")
            if isinstance(signal, dict):
                field = str(signal.get("field") or "").strip()
                if not field:
                    return ""
                for op in ("equals", "contains", "startswith", "regex"):
                    if op in signal:
                        return f"signal:{field} {op} {signal.get(op)!r}"
                for op in ("in", "any_of"):
                    if op in signal:
                        values = signal.get(op) or []
                        return f"signal:{field} {op} {values!r}"
                for op in ("gte", "lte", "gt", "lt", "exists"):
                    if op in signal:
                        return f"signal:{field} {op} {signal.get(op)!r}"
        return ""

    summary = _render(conditions)
    return summary[:400] if summary else "(no conditions)"


def retrieve_related_rules_for_runtime(
    *,
    session: Session,
    query: str,
    company_id: UUID | None,
    user_id: UUID | None = None,
    runtime_scope: RuleScope = RuleScope.prompt,
    limit: int = 5,
    model_name: str | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 20))
    query_text = str(query or "").strip()
    if not query_text:
        return []

    resolved_model = str(model_name or get_settings().rule_duplicate_embed_model)
    scope = runtime_scope if isinstance(runtime_scope, RuleScope) else RuleScope(str(runtime_scope))
    runtime_rules = RuleEngine().load_rules(
        session=session,
        company_id=company_id,
        user_id=user_id,
    )
    if not runtime_rules:
        return []

    runtime_by_id = {row.rule_id: row for row in runtime_rules}
    rows = list(
        session.exec(select(Rule).where(Rule.id.in_(list(runtime_by_id.keys())))).all()
    )
    if not rows:
        return []

    query_embedding = hash_rule_embedding_content(query_text)
    scored: list[tuple[float, int, int, float, float, Rule]] = []

    for row in rows:
        runtime_row = runtime_by_id.get(row.id)
        if runtime_row is None:
            continue
        if row.is_deleted:
            continue
        if row.scope != scope:
            continue
        if row.rag_mode == RagMode.off:
            continue
        if str(row.stable_key or "").strip().lower().startswith(_RAG_RULE_KEY_PREFIX):
            continue

        reference_text = build_rule_embedding_content(row)
        lexical_score = _lexical_score(query_text, reference_text)
        semantic_score = _cosine(query_embedding, upsert_rule_embedding(
            session=session,
            rule=row,
            model_name=resolved_model,
        ))
        hybrid_score = (semantic_score * 0.75) + (lexical_score * 0.25)
        if lexical_score <= 0.0 and semantic_score <= 0.0:
            continue

        rag_rank = 2 if row.rag_mode == RagMode.verify else 1
        scored.append(
            (
                hybrid_score,
                rag_rank,
                int(runtime_row.priority),
                semantic_score,
                lexical_score,
                row,
            )
        )

    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

    out: list[dict[str, Any]] = []
    for hybrid_score, _rag_rank, priority, semantic_score, lexical_score, row in scored[:safe_limit]:
        out.append(
            {
                "rule_id": str(row.id),
                "stable_key": str(row.stable_key),
                "name": str(row.name),
                "action": row.action.value,
                "scope": row.scope.value,
                "rag_mode": row.rag_mode.value,
                "origin": "global_default" if row.company_id is None else "company_custom",
                "priority": int(priority),
                "conditions_summary": summarize_rule_conditions(row.conditions or {}),
                "retrieval_score": round(float(hybrid_score), 4),
                "semantic_score": round(float(semantic_score), 4),
                "lexical_score": round(float(lexical_score), 4),
            }
        )
    return out


def load_linked_context_terms_by_rule_id(
    *,
    session: Session,
    rule_ids: Sequence[UUID],
) -> dict[UUID, list[ContextTerm]]:
    normalized_rule_ids = [UUID(str(x)) for x in list(rule_ids or []) if str(x)]
    if not normalized_rule_ids:
        return {}

    rows = list(
        session.exec(
            select(RuleContextTermLink, ContextTerm)
            .join(ContextTerm, ContextTerm.id == RuleContextTermLink.context_term_id)
            .where(RuleContextTermLink.rule_id.in_(normalized_rule_ids))
            .where(ContextTerm.enabled.is_(True))
            .order_by(RuleContextTermLink.created_at.desc(), ContextTerm.created_at.desc())
        ).all()
    )

    out: dict[UUID, list[ContextTerm]] = {rule_id: [] for rule_id in normalized_rule_ids}
    seen: set[tuple[UUID, UUID]] = set()
    for link_row, context_term in rows:
        key = (link_row.rule_id, context_term.id)
        if key in seen:
            continue
        seen.add(key)
        out.setdefault(link_row.rule_id, []).append(context_term)
    return out


def evaluate_semantic_assist_candidates(
    *,
    session: Session,
    query: str,
    runtime_rule_ids: Sequence[UUID],
    matched_context_keywords: Sequence[str] | None = None,
) -> dict[str, Any]:
    candidate_rule_ids = [UUID(str(x)) for x in list(runtime_rule_ids or []) if str(x)]
    if not candidate_rule_ids:
        return {
            "called": False,
            "candidate_rule_keys": [],
            "supported_rule_keys": [],
            "top_confidence": 0.0,
            "mode": "log_only",
        }

    rows = list(
        session.exec(
            select(Rule)
            .where(Rule.id.in_(candidate_rule_ids))
            .where(Rule.is_deleted.is_(False))
            .where(Rule.match_mode == MatchMode.keyword_plus_semantic)
            .order_by(Rule.priority.desc(), Rule.created_at.desc(), Rule.id.desc())
        ).all()
    )
    if not rows:
        return {
            "called": False,
            "candidate_rule_keys": [],
            "supported_rule_keys": [],
            "top_confidence": 0.0,
            "mode": "log_only",
        }

    context_terms_by_rule_id = load_linked_context_terms_by_rule_id(
        session=session,
        rule_ids=[row.id for row in rows],
    )
    query_text = str(query or "").strip()
    query_embedding = hash_rule_embedding_content(query_text)
    matched_keyword_set = {
        _normalize_phrase_identity(value)
        for value in list(matched_context_keywords or [])
        if _normalize_phrase_identity(value)
    }

    scores: list[SemanticAssistScore] = []
    top_confidence = 0.0
    for row in rows:
        linked_context_terms = context_terms_by_rule_id.get(row.id, [])
        reference_text = build_semantic_assist_rule_content(
            rule=row,
            context_terms=linked_context_terms,
        )
        linked_phrases = [
            str(term.term or "").strip()
            for term in linked_context_terms
            if str(term.term or "").strip()
        ]
        condition_phrases = _collect_condition_phrases(row.conditions or {})
        target_phrases, topic_phrases = _split_semantic_support_phrases(
            condition_phrases=condition_phrases,
            linked_phrases=linked_phrases,
            matched_keyword_set=matched_keyword_set,
        )
        lexical_score = _lexical_score(query_text, reference_text)
        semantic_score = _cosine(query_embedding, hash_rule_embedding_content(reference_text))
        target_anchor_score = _phrase_support_score(query_text, target_phrases)
        topic_phrase_score = _phrase_support_score(query_text, topic_phrases)
        confidence = (
            (semantic_score * 0.50)
            + (lexical_score * 0.10)
            + (topic_phrase_score * 0.35)
            + (target_anchor_score * 0.05)
        )
        top_confidence = max(top_confidence, float(confidence))
        # Phase-1 matched keywords act as the target anchor for semantic assist.
        # Without that anchor, topic-only semantic material should not support the rule.
        if condition_phrases and not target_phrases:
            continue
        if target_phrases and target_anchor_score <= 0.0:
            continue
        # Topic evidence is the only thing that can promote a rule into support.
        # Target-only matches stay as candidate relevance, not semantic support.
        if topic_phrases and topic_phrase_score <= 0.0:
            continue
        if confidence < _SEMANTIC_ASSIST_MIN_CONFIDENCE:
            continue
        scores.append(
            SemanticAssistScore(
                stable_key=str(row.stable_key),
                confidence=float(confidence),
                priority=int(row.priority),
            )
        )

    scores.sort(key=lambda item: (item.confidence, item.priority, item.stable_key), reverse=True)
    supported_rule_keys = [
        score.stable_key for score in scores[:_SEMANTIC_ASSIST_MAX_SUPPORTED]
    ]
    if scores:
        top_confidence = max(top_confidence, scores[0].confidence)

    return {
        "called": True,
        "candidate_rule_keys": [str(row.stable_key) for row in rows],
        "supported_rule_keys": supported_rule_keys,
        "top_confidence": round(float(top_confidence), 4),
        "mode": "log_only",
    }


def build_semantic_verify_material(
    *,
    session: Session,
    query: str,
    runtime_rule_ids: Sequence[UUID],
    supported_rule_key: str,
    matched_context_keywords: Sequence[str] | None = None,
) -> SemanticVerifyMaterial | None:
    candidate_rule_ids = [UUID(str(x)) for x in list(runtime_rule_ids or []) if str(x)]
    stable_key = str(supported_rule_key or "").strip()
    if not candidate_rule_ids or not stable_key:
        return None

    row = session.exec(
        select(Rule)
        .where(Rule.id.in_(candidate_rule_ids))
        .where(Rule.is_deleted.is_(False))
        .where(Rule.stable_key == stable_key)
        .where(Rule.match_mode == MatchMode.keyword_plus_semantic)
        .where(Rule.action == RuleAction.block)
        .order_by(Rule.priority.desc(), Rule.created_at.desc(), Rule.id.desc())
    ).first()
    if row is None:
        return None

    context_terms_by_rule_id = load_linked_context_terms_by_rule_id(
        session=session,
        rule_ids=[row.id],
    )
    linked_context_terms = context_terms_by_rule_id.get(row.id, [])
    linked_phrases = [
        str(term.term or "").strip()
        for term in linked_context_terms
        if str(term.term or "").strip()
    ]
    condition_phrases = _collect_condition_phrases(row.conditions or {})
    matched_keyword_set = {
        _normalize_phrase_identity(value)
        for value in list(matched_context_keywords or [])
        if _normalize_phrase_identity(value)
    }
    target_phrases, topic_phrases = _split_semantic_support_phrases(
        condition_phrases=condition_phrases,
        linked_phrases=linked_phrases,
        matched_keyword_set=matched_keyword_set,
    )

    return SemanticVerifyMaterial(
        rule_id=row.id,
        stable_key=str(row.stable_key),
        name=str(row.name or ""),
        description=str(row.description or ""),
        conditions=dict(row.conditions or {}),
        conditions_summary=summarize_rule_conditions(row.conditions or {}),
        linked_context_terms=linked_phrases,
        target_phrases=target_phrases,
        topic_phrases=topic_phrases,
        target_evidence=_collect_phrase_evidence(query, target_phrases),
        topic_evidence=_collect_phrase_evidence(query, topic_phrases),
    )


def _fold_vietnamese_text(text: str) -> str:
    raw = str(text or "").lower().replace("\u0111", "d")
    normalized = unicodedata.normalize("NFKD", raw)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _unicode_words(text: str) -> list[str]:
    raw = unicodedata.normalize("NFC", str(text or "").lower())
    words: list[str] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        if not buffer:
            return
        token = "".join(buffer).strip("_")
        buffer.clear()
        if not token:
            return
        if len(token) == 1 and not token.isdigit():
            return
        words.append(token)

    for ch in raw:
        category = unicodedata.category(ch)
        if ch.isalnum() or category.startswith("L") or category.startswith("N") or category.startswith("M"):
            buffer.append(ch)
            continue
        flush_buffer()

    flush_buffer()
    return words


def _build_shingles(words: list[str], size: int) -> set[str]:
    if size <= 1 or len(words) < size:
        return set()
    return {
        f"{size}g:" + " ".join(words[idx : idx + size])
        for idx in range(0, len(words) - size + 1)
    }


def _tokenize(text: str) -> set[str]:
    raw_text = str(text or "").strip().lower()
    if not raw_text:
        return set()

    folded_text = _fold_vietnamese_text(raw_text)
    raw_words = _unicode_words(raw_text)
    folded_words = _unicode_words(folded_text)

    tokens = set(raw_words) | set(folded_words)
    tokens |= _build_shingles(raw_words, 2)
    tokens |= _build_shingles(folded_words, 2)
    tokens |= _build_shingles(raw_words, 3)
    tokens |= _build_shingles(folded_words, 3)
    return {token for token in tokens if token}


def _collect_condition_phrases(node: Any) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        signal = node.get("signal")
        if isinstance(signal, dict):
            for op in ("equals", "contains", "startswith", "regex"):
                if op in signal:
                    value = str(signal.get(op) or "").strip()
                    if value:
                        out.append(value)
            for op in ("in", "any_of", "all_of"):
                raw = signal.get(op)
                if isinstance(raw, list):
                    for item in raw:
                        value = str(item or "").strip()
                        if value:
                            out.append(value)
                elif isinstance(raw, str):
                    value = raw.strip()
                    if value:
                        out.append(value)
        for value in node.values():
            out.extend(_collect_condition_phrases(value))
        return out
    if isinstance(node, list):
        for item in node:
            out.extend(_collect_condition_phrases(item))
    return out


def _normalize_phrase_identity(value: str | None) -> str:
    return str(value or "").strip().lower()


def _split_semantic_support_phrases(
    *,
    condition_phrases: Sequence[str],
    linked_phrases: Sequence[str],
    matched_keyword_set: set[str],
) -> tuple[list[str], list[str]]:
    normalized_condition_phrases: list[str] = []
    seen_condition_keys: set[str] = set()
    for phrase in condition_phrases:
        cleaned = str(phrase or "").strip()
        normalized = _normalize_phrase_identity(cleaned)
        if not normalized or normalized in seen_condition_keys:
            continue
        seen_condition_keys.add(normalized)
        normalized_condition_phrases.append(cleaned)

    target_keys = {
        _normalize_phrase_identity(phrase)
        for phrase in normalized_condition_phrases
        if _normalize_phrase_identity(phrase) in matched_keyword_set
    }
    target_phrases = [
        phrase
        for phrase in normalized_condition_phrases
        if _normalize_phrase_identity(phrase) in target_keys
    ]

    topic_phrases: list[str] = []
    seen_topic_keys: set[str] = set()

    for phrase in normalized_condition_phrases:
        normalized = _normalize_phrase_identity(phrase)
        if not normalized or normalized in target_keys or normalized in seen_topic_keys:
            continue
        seen_topic_keys.add(normalized)
        topic_phrases.append(phrase)

    for phrase in linked_phrases:
        cleaned = str(phrase or "").strip()
        normalized = _normalize_phrase_identity(cleaned)
        if not normalized or normalized in target_keys or normalized in seen_topic_keys:
            continue
        seen_topic_keys.add(normalized)
        topic_phrases.append(cleaned)

    return target_phrases, topic_phrases


def _collect_phrase_evidence(query: str, phrases: Sequence[str]) -> list[str]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    out: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        cleaned = str(phrase or "").strip()
        normalized = _normalize_phrase_identity(cleaned)
        if not normalized or normalized in seen:
            continue
        phrase_tokens = _tokenize(cleaned)
        if phrase_tokens and (query_tokens & phrase_tokens):
            seen.add(normalized)
            out.append(cleaned)
    return out


def _phrase_support_score(query: str, phrases: Sequence[str]) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0

    scores: list[float] = []
    seen: set[str] = set()
    for phrase in phrases:
        normalized_phrase = str(phrase or "").strip().lower()
        if not normalized_phrase or normalized_phrase in seen:
            continue
        seen.add(normalized_phrase)
        phrase_tokens = _tokenize(normalized_phrase)
        if not phrase_tokens:
            continue
        overlap = len(query_tokens & phrase_tokens)
        if overlap <= 0:
            continue
        scores.append(float(overlap / max(1, len(phrase_tokens))))

    if not scores:
        return 0.0

    scores.sort(reverse=True)
    top_scores = scores[:2]
    return float(sum(top_scores) / len(top_scores))


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


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return float(sum(float(a[i]) * float(b[i]) for i in range(n)))
