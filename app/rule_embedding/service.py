from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.common.enums import RagMode, RuleScope
from app.core.config import get_settings
from app.rule.engine import RuleEngine
from app.rule.model import Rule
from app.rule_embedding.model import RuleEmbedding


EMBED_DIM = 1536
_RAG_RULE_KEY_PREFIX = "global.security.rag."


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


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return float(sum(float(a[i]) * float(b[i]) for i in range(n)))
