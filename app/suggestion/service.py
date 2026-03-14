from __future__ import annotations

import asyncio
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.common.enums import (
    MemberRole,
    RagMode,
    RuleAction,
    RuleScope,
    RuleSeverity,
)
from app.common.error_codes import ErrorCode
from app.common.errors import AppError
from app.company.model import Company
from app.core.config import get_settings
from app.decision.context_scorer import ContextScorer
from app.decision.context_term_runtime import load_context_runtime_overrides
from app.decision.decision_resolver import DecisionResolver
from app.decision.detectors.local_regex_detector import LocalRegexDetector
from app.llm import generate_text_sync
from app.permissions.core import forbid, not_found
from app.permissions.loaders.conversation import load_company_member_active_or_403
from app.rag.models.context_term import ContextTerm
from app.rule.engine import RuleEngine, RuleMatch, RuleRuntime
from app.rule.model import Rule
from app.suggestion.models.rule_suggestion import RuleSuggestion
from app.suggestion.models.rule_suggestion_log import RuleSuggestionLog
from app.suggestion.duplicate_checker import build_duplicate_check
from app.suggestion.schemas import (
    DuplicateDecision,
    RuleSuggestionApplyIn,
    RuleSuggestionApplyOut,
    RuleSuggestionConfirmIn,
    RuleSuggestionDraftContextTerm,
    RuleSuggestionDraftPayload,
    RuleSuggestionDraftRule,
    RuleSuggestionEditIn,
    RuleSuggestionExplanationOut,
    RuleSuggestionGenerateOut,
    RuleSuggestionGenerateIn,
    RuleSuggestionGetOut,
    RuleSuggestionLogOut,
    RuleSuggestionOut,
    RuleSuggestionQualitySignalsOut,
    RuleSuggestionRejectIn,
    RuleSuggestionRetrievalContextOut,
    RuleSuggestionSimulateIn,
    RuleSuggestionSimulateOut,
    RuleSuggestionSimulateResultOut,
    SuggestionStatus,
)


SUGGESTION_TTL_DAYS = 7
_SUGGESTION_POLICY_EMBED_MODEL = "mxbai-embed-large"
_SUGGESTION_POLICY_EMBED_DIM = 1024

_SIMULATE_DETECTOR = LocalRegexDetector()
_SIMULATE_CONTEXT_SCORER = ContextScorer("app/config/context_base.yaml")
_SIMULATE_RULE_ENGINE = RuleEngine()
_SIMULATE_RESOLVER = DecisionResolver()

_ABSTRACT_CONTEXT_KEYWORDS = {
    "exact",
    "token",
    "secret",
    "internal",
    "internal code",
    "custom secret",
    "proprietary",
    "identifier",
    "code",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_non_empty(*, value: str | None, field: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid {field}",
            details=[{"field": field, "reason": "empty_after_trim"}],
        )
    return normalized


def _normalize_stable_key(value: str) -> str:
    return _normalize_non_empty(value=value, field="stable_key").lower()


def _normalize_term(value: str) -> str:
    return " ".join(_normalize_non_empty(value=value, field="term").lower().split())


def _normalize_lang(value: str) -> str:
    return _normalize_non_empty(value=value, field="lang").lower()


def _load_company_or_404(*, session: Session, company_id: UUID) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise not_found("Company not found", field="company_id")
    return company


def _require_company_admin(*, session: Session, company_id: UUID, user_id: UUID) -> None:
    member = load_company_member_active_or_403(
        session=session,
        company_id=company_id,
        user_id=user_id,
    )
    if member.role != MemberRole.company_admin:
        raise forbid(
            "Company admin required",
            field="company_id",
            reason="not_company_admin",
        )


def _parse_json_object(raw: str) -> dict[str, Any]:
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty_response")
    try:
        return json.loads(s)
    except Exception:
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(s[start : end + 1])
        raise


ENTITY_TYPE_PATTERN = re.compile(r"^[A-Z0-9_]+$")
SIGNAL_OPERATOR_KEYS = {
    "exists",
    "equals",
    "in",
    "contains",
    "any_of",
    "gte",
    "lte",
    "gt",
    "lt",
    "startswith",
    "regex",
}


def _raise_invalid_conditions(*, field: str, reason: str) -> None:
    raise AppError(
        422,
        ErrorCode.VALIDATION_ERROR,
        "Invalid rule conditions",
        details=[{"field": field, "reason": reason}],
    )


def _split_entity_types(*, raw_value: str, field: str) -> list[str]:
    normalized = _normalize_non_empty(value=raw_value, field=field).upper()
    raw_parts = [x.strip() for x in re.split(r"[|,;/]+", normalized) if x.strip()]
    if not raw_parts:
        _raise_invalid_conditions(field=field, reason="empty_entity_type")

    out: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        if not ENTITY_TYPE_PATTERN.match(part):
            _raise_invalid_conditions(field=field, reason="invalid_entity_type_format")
        if part in seen:
            continue
        seen.add(part)
        out.append(part)
    return out


def _normalize_signal_operator_value(*, op: str, value: Any, field: str) -> Any:
    if op == "exists":
        return bool(value)

    if op in {"in", "any_of"}:
        raw_values: list[Any]
        if isinstance(value, list):
            raw_values = value
        elif isinstance(value, str):
            raw_values = [x.strip() for x in re.split(r"[|,;/]+", value) if x.strip()]
        else:
            _raise_invalid_conditions(field=field, reason="operator_requires_list")
        out = [str(x).strip() for x in raw_values if str(x).strip()]
        if not out:
            _raise_invalid_conditions(field=field, reason="operator_list_empty")
        return out

    if op in {"gte", "lte", "gt", "lt"}:
        try:
            return float(value)
        except Exception:
            _raise_invalid_conditions(field=field, reason="operator_requires_number")

    if op in {"contains", "startswith", "regex"}:
        text = str(value or "").strip()
        if not text:
            _raise_invalid_conditions(field=field, reason="operator_requires_non_empty_value")
        return text

    if op == "equals":
        return value

    _raise_invalid_conditions(field=field, reason="unsupported_signal_operator")


def _normalize_signal_leaf(*, signal: Any, field: str) -> dict[str, Any]:
    if not isinstance(signal, dict):
        _raise_invalid_conditions(field=field, reason="signal_must_be_object")

    signal_field = _normalize_non_empty(
        value=str(signal.get("field", "")),
        field=f"{field}.field",
    )
    operators = [k for k in SIGNAL_OPERATOR_KEYS if k in signal]
    if len(operators) != 1:
        _raise_invalid_conditions(
            field=field,
            reason="signal_requires_exactly_one_operator",
        )
    op = operators[0]
    value = _normalize_signal_operator_value(
        op=op,
        value=signal.get(op),
        field=f"{field}.{op}",
    )
    return {"signal": {"field": signal_field, op: value}}


def _normalize_conditions_node(node: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(node, dict):
        _raise_invalid_conditions(field=field, reason="condition_node_not_dict")

    if "any" in node:
        children = node.get("any")
        if not isinstance(children, list):
            _raise_invalid_conditions(field=f"{field}.any", reason="must_be_list")
        if not children:
            _raise_invalid_conditions(field=f"{field}.any", reason="empty_list")
        normalized_children: list[dict[str, Any]] = [
            _normalize_conditions_node(child, field=f"{field}.any[{idx}]")
            for idx, child in enumerate(children)
        ]
        flattened: list[dict[str, Any]] = []
        for child in normalized_children:
            if isinstance(child, dict) and set(child.keys()) == {"any"}:
                inner = child.get("any")
                if isinstance(inner, list):
                    flattened.extend(x for x in inner if isinstance(x, dict))
                    continue
            flattened.append(child)
        if not flattened:
            _raise_invalid_conditions(field=f"{field}.any", reason="empty_after_normalize")
        return {"any": flattened}

    if "all" in node:
        children = node.get("all")
        if not isinstance(children, list):
            _raise_invalid_conditions(field=f"{field}.all", reason="must_be_list")
        if not children:
            _raise_invalid_conditions(field=f"{field}.all", reason="empty_list")
        normalized_children: list[dict[str, Any]] = [
            _normalize_conditions_node(child, field=f"{field}.all[{idx}]")
            for idx, child in enumerate(children)
        ]
        flattened: list[dict[str, Any]] = []
        for child in normalized_children:
            if isinstance(child, dict) and set(child.keys()) == {"all"}:
                inner = child.get("all")
                if isinstance(inner, list):
                    flattened.extend(x for x in inner if isinstance(x, dict))
                    continue
            flattened.append(child)
        if not flattened:
            _raise_invalid_conditions(field=f"{field}.all", reason="empty_after_normalize")
        return {"all": flattened}

    if "not" in node:
        return {
            "not": _normalize_conditions_node(
                node.get("not"),
                field=f"{field}.not",
            )
        }

    if "entity_type" in node:
        entity_types = _split_entity_types(
            raw_value=str(node.get("entity_type", "")),
            field=f"{field}.entity_type",
        )
        leaf_base: dict[str, Any] = {}
        if "min_score" in node:
            try:
                leaf_base["min_score"] = float(node["min_score"])
            except Exception:
                _raise_invalid_conditions(
                    field=f"{field}.min_score",
                    reason="must_be_number",
                )
        if "max_score" in node:
            try:
                leaf_base["max_score"] = float(node["max_score"])
            except Exception:
                _raise_invalid_conditions(
                    field=f"{field}.max_score",
                    reason="must_be_number",
                )
        if "min_score" in leaf_base and "max_score" in leaf_base:
            if float(leaf_base["min_score"]) > float(leaf_base["max_score"]):
                _raise_invalid_conditions(
                    field=field,
                    reason="min_score_gt_max_score",
                )
        if "source" in node:
            source = node.get("source")
            if isinstance(source, str):
                src = source.strip()
                if not src:
                    _raise_invalid_conditions(
                        field=f"{field}.source",
                        reason="empty_source",
                    )
                leaf_base["source"] = src
            elif isinstance(source, list):
                src_list = [str(x).strip() for x in source if str(x).strip()]
                if not src_list:
                    _raise_invalid_conditions(
                        field=f"{field}.source",
                        reason="empty_source",
                    )
                leaf_base["source"] = src_list
            else:
                _raise_invalid_conditions(
                    field=f"{field}.source",
                    reason="invalid_source_type",
                )

        if len(entity_types) == 1:
            return {"entity_type": entity_types[0], **leaf_base}
        return {"any": [{"entity_type": et, **leaf_base} for et in entity_types]}

    if "signal" in node:
        return _normalize_signal_leaf(signal=node.get("signal"), field=f"{field}.signal")

    _raise_invalid_conditions(field=field, reason="unsupported_node")


def _normalize_draft(payload: RuleSuggestionDraftPayload) -> RuleSuggestionDraftPayload:
    rule = payload.rule
    normalized_conditions = _normalize_conditions_node(
        rule.conditions,
        field="draft.rule.conditions",
    )
    action = RuleAction.mask if rule.action == RuleAction.warn else rule.action

    normalized_rule = RuleSuggestionDraftRule(
        stable_key=_normalize_stable_key(rule.stable_key),
        name=_normalize_non_empty(value=rule.name, field="name"),
        description=(rule.description or "").strip() or None,
        scope=rule.scope,
        conditions=normalized_conditions,
        action=action,
        severity=rule.severity,
        priority=int(rule.priority),
        rag_mode=rule.rag_mode,
        enabled=bool(rule.enabled),
    )

    normalized_terms: list[RuleSuggestionDraftContextTerm] = []
    dedupe_terms: set[tuple[str, str, str]] = set()
    for t in payload.context_terms:
        term = _normalize_term(t.term)
        lang = _normalize_lang(t.lang)
        entity_types = _split_entity_types(
            raw_value=t.entity_type,
            field="context_terms.entity_type",
        )
        for entity_type in entity_types:
            key = (entity_type, term, lang)
            if key in dedupe_terms:
                continue
            dedupe_terms.add(key)

            normalized_terms.append(
                RuleSuggestionDraftContextTerm(
                    entity_type=entity_type,
                    term=term,
                    lang=lang,
                    weight=float(t.weight),
                    window_1=max(0, int(t.window_1)),
                    window_2=max(0, int(t.window_2)),
                    enabled=bool(t.enabled),
                )
            )

    return RuleSuggestionDraftPayload(rule=normalized_rule, context_terms=normalized_terms)


def _draft_to_json(payload: RuleSuggestionDraftPayload) -> dict[str, Any]:
    return payload.model_dump(mode="json")


def _canonical_rule_for_dedupe(rule: RuleSuggestionDraftRule) -> dict[str, Any]:
    return {
        "scope": rule.scope.value,
        "conditions": rule.conditions,
        "action": rule.action.value,
        "severity": rule.severity.value,
        "priority": int(rule.priority),
        "rag_mode": rule.rag_mode.value,
        "enabled": bool(rule.enabled),
    }


def _canonical_terms_for_dedupe(
    terms: list[RuleSuggestionDraftContextTerm],
) -> list[dict[str, Any]]:
    out = [
        {
            "entity_type": t.entity_type,
            "term": t.term,
            "lang": t.lang,
            "weight": float(t.weight),
            "window_1": int(t.window_1),
            "window_2": int(t.window_2),
            "enabled": bool(t.enabled),
        }
        for t in terms
    ]
    out.sort(
        key=lambda x: (
            str(x["entity_type"]),
            str(x["term"]),
            str(x["lang"]),
            float(x["weight"]),
            int(x["window_1"]),
            int(x["window_2"]),
            bool(x["enabled"]),
        )
    )
    return out


def _dedupe_key(*, company_id: UUID, payload: RuleSuggestionDraftPayload) -> str:
    body = {
        "company_id": str(company_id),
        "type": "rule_with_context",
        "rule": _canonical_rule_for_dedupe(payload.rule),
        "context_terms": _canonical_terms_for_dedupe(payload.context_terms),
    }
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _snapshot_suggestion(row: RuleSuggestion) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "created_by": str(row.created_by),
        "status": row.status,
        "type": row.type,
        "version": int(row.version),
        "nl_input": row.nl_input,
        "dedupe_key": row.dedupe_key,
        "draft_json": row.draft_json,
        "approve_reason": row.approve_reason,
        "reject_reason": row.reject_reason,
        "applied_result_json": row.applied_result_json,
        "approved_by": str(row.approved_by) if row.approved_by else None,
        "rejected_by": str(row.rejected_by) if row.rejected_by else None,
        "applied_by": str(row.applied_by) if row.applied_by else None,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "rejected_at": row.rejected_at.isoformat() if row.rejected_at else None,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


def _append_log(
    *,
    session: Session,
    suggestion_id: UUID,
    company_id: UUID,
    actor_user_id: UUID,
    action: str,
    reason: str | None = None,
    before_json: dict[str, Any] | None = None,
    after_json: dict[str, Any] | None = None,
) -> None:
    session.add(
        RuleSuggestionLog(
            suggestion_id=suggestion_id,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action=action,
            reason=(reason or "").strip() or None,
            before_json=before_json,
            after_json=after_json,
        )
    )


def _to_out(row: RuleSuggestion) -> RuleSuggestionOut:
    return RuleSuggestionOut(
        id=row.id,
        rule_set_id=row.company_id,
        created_by=row.created_by,
        status=SuggestionStatus(row.status),
        type=row.type,
        version=row.version,
        nl_input=row.nl_input,
        dedupe_key=row.dedupe_key,
        draft=RuleSuggestionDraftPayload.model_validate(row.draft_json),
        applied_result_json=row.applied_result_json,
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_log_out(row: RuleSuggestionLog) -> RuleSuggestionLogOut:
    return RuleSuggestionLogOut(
        id=row.id,
        suggestion_id=row.suggestion_id,
        rule_set_id=row.company_id,
        actor_user_id=row.actor_user_id,
        action=row.action,
        reason=row.reason,
        before_json=row.before_json,
        after_json=row.after_json,
        created_at=row.created_at,
    )


def _action_key(value: RuleAction | str | None) -> str:
    if hasattr(value, "value"):
        raw = str(getattr(value, "value") or "").strip().upper()
    else:
        raw = str(value or "").strip().upper()

    if raw == "BLOCK":
        return "BLOCK"
    if raw == "MASK":
        return "MASK"
    return "ALLOW"


def _collect_simulation_exact_terms_from_draft(
    *,
    draft: RuleSuggestionDraftPayload,
    limit: int = 32,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    safe_limit = max(1, int(limit))

    for term in draft.context_terms:
        et = str(term.entity_type or "").strip().upper()
        if et not in {"INTERNAL_CODE", "CUSTOM_SECRET", "PROPRIETARY_IDENTIFIER"}:
            continue
        text = _fold_text(str(term.term or ""))
        if len(text) < 4 or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= safe_limit:
            break
    return out


def _match_simulation_exact_terms_in_text(
    *,
    text: str,
    exact_terms: list[str],
    limit: int = 20,
) -> list[str]:
    if not exact_terms:
        return []

    raw_text = str(text or "").lower()
    fold_text = _fold_text(text)
    out: list[str] = []
    seen: set[str] = set()
    safe_limit = max(1, int(limit))

    for term in exact_terms:
        normalized_term = _fold_text(str(term or ""))
        if len(normalized_term) < 4 or normalized_term in seen:
            continue
        if normalized_term in raw_text or normalized_term in fold_text:
            seen.add(normalized_term)
            out.append(normalized_term)
            if len(out) >= safe_limit:
                break
    return out


def _merge_simulation_context_keywords(
    *,
    context_keywords: list[str],
    extra_keywords: list[str],
    limit: int = 24,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in list(context_keywords) + list(extra_keywords):
        item = _fold_text(str(value or ""))
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _compile_transient_runtime_rule(
    *,
    suggestion_id: UUID,
    draft_rule: RuleSuggestionDraftRule,
) -> RuleRuntime:
    return RuleRuntime(
        rule_id=suggestion_id,
        stable_key=draft_rule.stable_key,
        name=draft_rule.name,
        action=draft_rule.action,
        priority=int(draft_rule.priority),
        conditions=draft_rule.conditions,
    )


def _build_simulation_runtime_rules(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    draft_rule: RuleSuggestionDraftRule,
) -> list[RuleRuntime]:
    base_rules = _SIMULATE_RULE_ENGINE.load_rules(
        session=session,
        company_id=company_id,
        user_id=None,
    )
    merged = [r for r in base_rules if str(r.stable_key) != str(draft_rule.stable_key)]
    if draft_rule.enabled:
        merged.append(
            _compile_transient_runtime_rule(
                suggestion_id=suggestion_id,
                draft_rule=draft_rule,
            )
        )
    merged.sort(key=lambda r: int(r.priority), reverse=True)
    return merged


def _evaluate_with_runtime_rules(
    *,
    runtime_rules: list[RuleRuntime],
    entities: list[Any],
    signals: dict[str, Any],
) -> list[RuleMatch]:
    normalized_signals = _SIMULATE_RULE_ENGINE._normalize_signals(dict(signals))
    out: list[RuleMatch] = []
    for runtime_rule in runtime_rules:
        try:
            if _SIMULATE_RULE_ENGINE._match_conditions(
                runtime_rule.conditions or {},
                entities=entities,
                signals=normalized_signals,
            ):
                out.append(
                    RuleMatch(
                        rule_id=runtime_rule.rule_id,
                        stable_key=runtime_rule.stable_key,
                        name=runtime_rule.name,
                        action=runtime_rule.action,
                        priority=int(runtime_rule.priority),
                    )
                )
        except Exception:
            continue
    return out


def _load_suggestion_row_or_404(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
) -> RuleSuggestion:
    row = session.get(RuleSuggestion, suggestion_id)
    if not row or row.company_id != company_id:
        raise not_found("Suggestion not found", field="suggestion_id")
    return row


_INSIGHT_STOP_WORDS = {
    "va",
    "voi",
    "cho",
    "mot",
    "nhung",
    "cac",
    "tao",
    "ta",
    "hay",
    "toi",
    "the",
    "that",
    "this",
    "from",
    "with",
    "for",
    "and",
    "rule",
    "rules",
}


def _extract_entity_types(node: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            if "entity_type" in value:
                raw = str(value.get("entity_type") or "").upper()
                parts = [x.strip() for x in re.split(r"[|,;/]+", raw) if x.strip()]
                for part in parts:
                    if part in seen:
                        continue
                    seen.add(part)
                    out.append(part)
            for child in value.values():
                _walk(child)
            return
        if isinstance(value, list):
            for child in value:
                _walk(child)

    _walk(node)
    return out


def _extract_persona_hint(node: Any) -> str | None:
    if isinstance(node, dict):
        signal = node.get("signal")
        if isinstance(signal, dict):
            field = str(signal.get("field") or "").strip().lower()
            if field == "persona":
                equals = str(signal.get("equals") or "").strip().lower()
                if equals:
                    return equals
                raw_any = signal.get("any_of")
                if isinstance(raw_any, list):
                    for item in raw_any:
                        text = str(item or "").strip().lower()
                        if text:
                            return text
        for child in node.values():
            found = _extract_persona_hint(child)
            if found:
                return found
        return None
    if isinstance(node, list):
        for child in node:
            found = _extract_persona_hint(child)
            if found:
                return found
    return None


def _extract_signal_fields(node: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            signal = value.get("signal")
            if isinstance(signal, dict):
                field_name = str(signal.get("field") or "").strip().lower()
                if field_name and field_name not in seen:
                    seen.add(field_name)
                    out.append(field_name)
            for child in value.values():
                _walk(child)
            return
        if isinstance(value, list):
            for child in value:
                _walk(child)

    _walk(node)
    return out


def _prompt_keywords(prompt: str, *, limit: int = 6) -> list[str]:
    folded = _fold_text(prompt)
    parts = [p.strip() for p in re.split(r"[^a-zA-Z0-9_]+", folded) if p.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if len(part) < 3:
            continue
        if part in _INSIGHT_STOP_WORDS:
            continue
        if part in seen:
            continue
        seen.add(part)
        out.append(part)
        if len(out) >= limit:
            break
    return out


def _derive_terms(prompt: str, draft: RuleSuggestionDraftPayload) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    prompt_code_terms = _prompt_code_like_terms(prompt)
    allow_unprompted_code_terms = _is_custom_secret_prompt(prompt)

    for term in draft.context_terms:
        text = _fold_text(term.term)
        if (
            text
            and _is_code_like_term(text)
            and (not allow_unprompted_code_terms)
            and text not in prompt_code_terms
        ):
            continue
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)

    for entity_type in _extract_entity_types(draft.rule.conditions):
        label = entity_type.lower()
        if label in seen:
            continue
        seen.add(label)
        out.append(label)

    for field_name in _extract_signal_fields(draft.rule.conditions):
        if field_name in seen:
            continue
        seen.add(field_name)
        out.append(field_name)

    for kw in _prompt_keywords(prompt, limit=8):
        if kw in seen:
            continue
        seen.add(kw)
        out.append(kw)

    return out[:8]


def _detected_intent(prompt: str, draft: RuleSuggestionDraftPayload) -> str:
    persona = _extract_persona_hint(draft.rule.conditions)
    entity_types = _extract_entity_types(draft.rule.conditions)
    if persona:
        return f"{persona}_{draft.rule.action.value}_policy"
    if entity_types:
        slug = "_".join(x.lower() for x in entity_types[:2])
        return f"protect_{slug}"
    if _is_finance_prompt(prompt):
        return "finance_policy_control"
    return f"{draft.rule.scope.value}_{draft.rule.action.value}_control"


def _summary_text(*, draft: RuleSuggestionDraftPayload) -> str:
    entity_types = _extract_entity_types(draft.rule.conditions)
    if entity_types:
        target = ", ".join(entity_types[:2])
        return (
            f"Rule '{draft.rule.name}' proposes {draft.rule.action.value} in "
            f"{draft.rule.scope.value} scope for {target} related content."
        )
    return (
        f"Rule '{draft.rule.name}' proposes {draft.rule.action.value} "
        f"in {draft.rule.scope.value} scope."
    )


def _action_reason_text(
    *,
    action: RuleAction,
    duplicate_decision: str,
) -> str:
    if action == RuleAction.block:
        reason = "Prompt intent indicates strict prevention, so action is set to block."
    elif action == RuleAction.mask:
        reason = "Prompt intent focuses on redaction/protection, so action is set to mask."
    else:
        reason = f"Prompt intent aligns with action '{action.value}'."

    if duplicate_decision == DuplicateDecision.exact_duplicate.value:
        return reason + " Duplicate check indicates high overlap with an existing rule."
    if duplicate_decision == DuplicateDecision.near_duplicate.value:
        return reason + " Duplicate check indicates partial overlap with existing rules."
    return reason


def _normalize_generation_source(raw_source: str) -> str:
    source = str(raw_source or "").strip().lower()
    if source == "llm":
        return "llm"
    if "fallback" in source:
        return "heuristic_fallback"
    if source in {"none", ""}:
        return "unknown"
    return source


def _to_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _duplicate_risk(decision: str, confidence: float) -> str:
    if decision == DuplicateDecision.exact_duplicate.value:
        return "high"
    if decision == DuplicateDecision.near_duplicate.value:
        return "high" if confidence >= 0.8 else "medium"
    if decision == DuplicateDecision.different.value:
        return "low" if confidence >= 0.75 else "medium"
    return "medium"


def _intent_confidence(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
    generation_source: str,
    duplicate_risk: str,
    intent_guard_applied: bool = False,
    intent_mismatch_detected: bool = False,
    runtime_usable: bool = True,
    runtime_warning_count: int = 0,
) -> float:
    score = 0.55
    if len(_prompt_keywords(prompt, limit=12)) >= 3:
        score += 0.08
    if draft.context_terms:
        score += 0.10
    if _extract_entity_types(draft.rule.conditions) or _extract_signal_fields(
        draft.rule.conditions
    ):
        score += 0.10
    if _action_hint_from_prompt(prompt) == draft.rule.action:
        score += 0.08
    else:
        score -= 0.05
    if generation_source == "heuristic_fallback":
        score -= 0.12
    if duplicate_risk == "high":
        score -= 0.08
    elif duplicate_risk == "medium":
        score -= 0.03
    if intent_mismatch_detected and (not intent_guard_applied):
        score -= 0.16
    elif intent_mismatch_detected and intent_guard_applied:
        score -= 0.04
    if not runtime_usable:
        score -= 0.18
    elif runtime_warning_count > 0:
        score -= min(0.15, 0.05 * float(runtime_warning_count))
    return max(0.0, min(1.0, round(score, 4)))


def _build_suggestion_explanation(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
    duplicate_meta: dict[str, Any],
) -> RuleSuggestionExplanationOut:
    decision = str(duplicate_meta.get("decision") or DuplicateDecision.different.value).upper()
    return RuleSuggestionExplanationOut(
        summary=_summary_text(draft=draft),
        detected_intent=_detected_intent(prompt, draft),
        derived_terms=_derive_terms(prompt, draft),
        action_reason=_action_reason_text(action=draft.rule.action, duplicate_decision=decision),
    )


def _build_quality_signals(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
    duplicate_meta: dict[str, Any],
    generation_meta: dict[str, Any],
) -> RuleSuggestionQualitySignalsOut:
    decision = str(duplicate_meta.get("decision") or DuplicateDecision.different.value).upper()
    confidence = _to_float(duplicate_meta.get("confidence"), default=0.0)
    source = _normalize_generation_source(str(generation_meta.get("source") or "unknown"))
    duplicate_risk = _duplicate_risk(decision, confidence)
    retrieval_context = _build_retrieval_context(generation_meta=generation_meta)
    guard_meta = _extract_intent_guard_meta(generation_meta=generation_meta)
    runtime_meta = _extract_runtime_usability_meta(
        prompt=prompt,
        draft=draft,
        generation_meta=generation_meta,
    )
    runtime_warnings = _to_str_list(runtime_meta.get("warnings"))
    runtime_usable = bool(runtime_meta.get("runtime_usable", not runtime_warnings))
    if runtime_warnings:
        runtime_usable = False

    return RuleSuggestionQualitySignalsOut(
        intent_confidence=_intent_confidence(
            prompt=prompt,
            draft=draft,
            generation_source=source,
            duplicate_risk=duplicate_risk,
            intent_guard_applied=guard_meta["intent_guard_applied"],
            intent_mismatch_detected=guard_meta["intent_mismatch_detected"],
            runtime_usable=runtime_usable,
            runtime_warning_count=len(runtime_warnings),
        ),
        duplicate_risk=duplicate_risk,
        conflict_risk="unknown",
        generation_source=source,
        has_policy_context=bool(retrieval_context.has_policy_context),
        intent_guard_applied=guard_meta["intent_guard_applied"],
        intent_mismatch_detected=guard_meta["intent_mismatch_detected"],
        runtime_usable=runtime_usable,
        runtime_warnings=runtime_warnings,
    )


def _to_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _build_retrieval_context(
    *,
    generation_meta: dict[str, Any],
) -> RuleSuggestionRetrievalContextOut:
    payload = generation_meta.get("context_retrieval")
    if not isinstance(payload, dict):
        payload = {}

    policy_chunk_ids = _to_str_list(payload.get("policy_chunk_ids"))
    related_rule_ids = _to_str_list(payload.get("related_rule_ids"))

    has_policy_context = False
    if policy_chunk_ids:
        has_policy_context = True
    elif bool(payload.get("has_policy_context")):
        has_policy_context = True
    else:
        try:
            has_policy_context = int(payload.get("policy_chunks") or 0) > 0
        except Exception:
            has_policy_context = False

    return RuleSuggestionRetrievalContextOut(
        has_policy_context=bool(has_policy_context),
        policy_chunk_ids=policy_chunk_ids,
        related_rule_ids=related_rule_ids,
    )


def _extract_intent_guard_meta(*, generation_meta: dict[str, Any]) -> dict[str, bool]:
    payload = generation_meta.get("intent_guard")
    if not isinstance(payload, dict):
        return {"intent_guard_applied": False, "intent_mismatch_detected": False}
    return {
        "intent_guard_applied": bool(payload.get("applied", False)),
        "intent_mismatch_detected": bool(payload.get("mismatch_detected", False)),
    }


def _extract_runtime_usability_meta(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
    generation_meta: dict[str, Any],
) -> dict[str, Any]:
    inferred = _evaluate_runtime_usability(draft=draft, prompt=prompt)
    inferred_warnings = _to_str_list(inferred.get("warnings"))
    runtime_usable = bool(inferred.get("runtime_usable", not inferred_warnings))

    payload = generation_meta.get("runtime_usability")
    if isinstance(payload, dict):
        payload_warnings = _to_str_list(payload.get("warnings"))
        warnings = _to_str_list(inferred_warnings + payload_warnings)
        runtime_usable = (
            runtime_usable
            and bool(payload.get("runtime_usable", not payload_warnings))
            and (not payload_warnings)
        )
        if warnings:
            runtime_usable = False
        return {
            "runtime_usable": runtime_usable,
            "warnings": warnings,
        }
    return {
        "runtime_usable": runtime_usable,
        "warnings": inferred_warnings,
    }


def _load_generate_telemetry(
    *,
    session: Session,
    suggestion_id: UUID,
) -> tuple[dict[str, Any], dict[str, Any]]:
    row = session.exec(
        select(RuleSuggestionLog)
        .where(RuleSuggestionLog.suggestion_id == suggestion_id)
        .where(RuleSuggestionLog.action == "suggestion.generate.telemetry")
        .order_by(RuleSuggestionLog.created_at.desc())
        .limit(1)
    ).first()
    if row is None or not isinstance(row.after_json, dict):
        return {}, {}

    payload = row.after_json
    generation_meta = payload.get("draft_generation")
    duplicate_meta = payload.get("duplicate_check")
    if not isinstance(generation_meta, dict):
        generation_meta = {}
    if not isinstance(duplicate_meta, dict):
        duplicate_meta = {}
    return generation_meta, duplicate_meta


def _expire_if_needed(*, session: Session, row: RuleSuggestion) -> RuleSuggestion:
    if row.status in {
        SuggestionStatus.applied.value,
        SuggestionStatus.rejected.value,
        SuggestionStatus.expired.value,
        SuggestionStatus.failed.value,
    }:
        return row
    if row.expires_at and row.expires_at <= _utcnow():
        row.status = SuggestionStatus.expired.value
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def _find_active_duplicate(
    *,
    session: Session,
    company_id: UUID,
    dedupe_key: str,
    exclude_suggestion_id: UUID | None = None,
) -> RuleSuggestion | None:
    stmt = (
        select(RuleSuggestion)
        .where(RuleSuggestion.company_id == company_id)
        .where(RuleSuggestion.dedupe_key == dedupe_key)
        .where(
            RuleSuggestion.status.in_(
                [SuggestionStatus.draft.value, SuggestionStatus.approved.value]
            )
        )
        .order_by(RuleSuggestion.created_at.desc())
    )
    rows = list(session.exec(stmt).all())
    for row in rows:
        if exclude_suggestion_id and row.id == exclude_suggestion_id:
            continue
        row = _expire_if_needed(session=session, row=row)
        if row.status in {SuggestionStatus.draft.value, SuggestionStatus.approved.value}:
            return row
    return None


def _assert_expected_version(
    *,
    current_version: int,
    expected_version: int | None,
) -> None:
    if expected_version is None:
        return
    if int(expected_version) != int(current_version):
        raise AppError(
            409,
            ErrorCode.CONFLICT,
            "Suggestion version mismatch",
            details=[{"field": "expected_version", "reason": "stale_version"}],
        )


def _fold_text(value: str) -> str:
    raw = str(value or "").lower().replace("\u0111", "d")
    normalized = unicodedata.normalize("NFKD", raw)
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", no_marks).strip()


def _has_any(text: str, keys: list[str]) -> bool:
    t = _fold_text(text)
    return any(_fold_text(k) in t for k in keys if str(k or "").strip())


def _action_hint_from_prompt(prompt: str) -> RuleAction:
    p = prompt.lower()
    if _has_any(p, ["allow", "cho phep", "cho phép"]):
        return RuleAction.allow
    if _has_any(p, ["mask", "che", "che thong tin", "an thong tin", "ẩn thông tin"]):
        return RuleAction.mask
    if _has_any(p, ["block", "chan", "chặn"]):
        return RuleAction.block
    return RuleAction.mask


def _contains_entity_leaf(conditions: Any) -> bool:
    if isinstance(conditions, dict):
        if "entity_type" in conditions:
            return True
        return any(_contains_entity_leaf(v) for v in conditions.values())
    if isinstance(conditions, list):
        return any(_contains_entity_leaf(x) for x in conditions)
    return False


def _contains_entity_type(conditions: Any, entity_types: set[str]) -> bool:
    wanted = {str(x or "").strip().upper() for x in entity_types if str(x or "").strip()}
    if not wanted:
        return False
    if isinstance(conditions, dict):
        if "entity_type" in conditions:
            raw = str(conditions.get("entity_type") or "").upper()
            parts = [x.strip() for x in re.split(r"[|,;/]+", raw) if x.strip()]
            if any(part in wanted for part in parts):
                return True
        return any(_contains_entity_type(v, wanted) for v in conditions.values())
    if isinstance(conditions, list):
        return any(_contains_entity_type(x, wanted) for x in conditions)
    return False


def _has_signal_persona(conditions: Any, persona: str) -> bool:
    wanted = str(persona or "").strip().lower()
    if not wanted:
        return False
    if isinstance(conditions, dict):
        signal = conditions.get("signal")
        if isinstance(signal, dict):
            field_name = str(signal.get("field") or "").strip().lower()
            if field_name == "persona":
                if str(signal.get("equals") or "").strip().lower() == wanted:
                    return True
                raw_any = signal.get("any_of")
                if isinstance(raw_any, list):
                    values = {str(x or "").strip().lower() for x in raw_any}
                    if wanted in values:
                        return True
        return any(_has_signal_persona(v, wanted) for v in conditions.values())
    if isinstance(conditions, list):
        return any(_has_signal_persona(x, wanted) for x in conditions)
    return False


def _is_finance_prompt(prompt: str) -> bool:
    p = (prompt or "").lower()
    finance_keys = [
        "tai chinh",
        "bao cao tai chinh",
        "doanh thu",
        "loi nhuan",
        "ke toan",
        "financial",
        "finance",
        "revenue",
        "profit",
        "p&l",
    ]
    return _has_any(p, finance_keys)


def _mentions_tax_id(prompt: str) -> bool:
    p = (prompt or "").lower()
    return _has_any(
        p,
        [
            "tax",
            "tax id",
            "tax code",
            "mst",
            "ma so thue",
            "tin",
        ],
    )


_CODE_LIKE_TOKEN_PATTERN = re.compile(
    r"\b[A-Za-z0-9]{2,}(?:[-_][A-Za-z0-9]{1,}){1,}\b"
)


def _extract_code_like_tokens(prompt: str, *, limit: int = 4) -> list[str]:
    raw = str(prompt or "")
    out: list[str] = []
    seen: set[str] = set()
    for m in _CODE_LIKE_TOKEN_PATTERN.finditer(raw):
        token = str(m.group(0) or "").strip()
        if not token:
            continue
        upper = token.upper()
        # Avoid plain natural-language fragments; keep code-ish token shapes.
        if upper.count("-") + upper.count("_") < 1:
            continue
        if not any(ch.isdigit() for ch in upper) and len(upper) < 12:
            continue
        if upper in seen:
            continue
        seen.add(upper)
        out.append(upper)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _is_internal_secret_wording(prompt: str) -> bool:
    p = (prompt or "").lower()
    return _has_any(
        p,
        [
            "ma noi bo",
            "mã nội bộ",
            "token noi bo",
            "token nội bộ",
            "chuoi bi mat",
            "chuỗi bí mật",
            "secret",
            "internal code",
            "internal token",
            "proprietary",
            "proprietary identifier",
            "identifier noi bo",
        ],
    )


def _is_custom_secret_prompt(prompt: str) -> bool:
    tokens = _extract_code_like_tokens(prompt)
    if not tokens:
        return False
    if _is_internal_secret_wording(prompt):
        return True
    p = (prompt or "").lower()
    return _has_any(p, ["token", "secret", "noi bo", "nội bộ"])


def _is_payroll_prompt(prompt: str) -> bool:
    p = (prompt or "").lower()
    return _has_any(
        p,
        [
            "payroll",
            "salary",
            "luong",
            "lương",
            "bang luong",
            "bảng lương",
            "danh sach luong",
            "danh sách lương",
            "employee compensation",
            "compensation",
        ],
    )


def _mentions_external_or_personal_email(prompt: str) -> bool:
    p = (prompt or "").lower()
    return _has_any(
        p,
        [
            "gmail",
            "personal email",
            "email ca nhan",
            "email cá nhân",
            "email ngoai",
            "email ngoài",
            "email ngoai cong ty",
            "email ngoài công ty",
            "outside company",
            "external email",
            "email ben ngoai",
            "email bên ngoài",
        ],
    )


def _is_payroll_external_email_prompt(prompt: str) -> bool:
    return _is_payroll_prompt(prompt) and _mentions_external_or_personal_email(prompt)


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
        stable_key=f"company.custom.suggested.{stable_suffix}",
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
                entity_type="PERSONA_OFFICE",
                term=term,
                lang="vi",
                weight=1.0,
                window_1=80,
                window_2=24,
                enabled=True,
            )
        )
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
        stable_key=f"company.custom.suggested.{stable_suffix}",
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


def _condition_has_context_keyword_term(conditions: Any, term: str) -> bool:
    wanted = str(term or "").strip().lower()
    if not wanted:
        return False
    if isinstance(conditions, dict):
        signal = conditions.get("signal")
        if isinstance(signal, dict):
            field_name = str(signal.get("field") or "").strip().lower()
            if field_name == "context_keywords":
                values: set[str] = set()
                any_of = signal.get("any_of")
                if isinstance(any_of, list):
                    values.update(str(x or "").strip().lower() for x in any_of)
                in_values = signal.get("in")
                if isinstance(in_values, list):
                    values.update(str(x or "").strip().lower() for x in in_values)
                equals = signal.get("equals")
                if equals is not None:
                    values.add(str(equals or "").strip().lower())
                contains = signal.get("contains")
                if contains is not None:
                    values.add(str(contains or "").strip().lower())

                for value in values:
                    if not value:
                        continue
                    if wanted == value or wanted in value or value in wanted:
                        return True
        return any(_condition_has_context_keyword_term(v, wanted) for v in conditions.values())
    if isinstance(conditions, list):
        return any(_condition_has_context_keyword_term(x, wanted) for x in conditions)
    return False


def _collect_context_keyword_terms(conditions: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def _push(value: Any) -> None:
        text = _fold_text(str(value or ""))
        if not text or text in seen:
            return
        seen.add(text)
        out.append(text)

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            signal = node.get("signal")
            if isinstance(signal, dict):
                field_name = _fold_text(str(signal.get("field") or ""))
                if field_name == "context_keywords":
                    any_of = signal.get("any_of")
                    if isinstance(any_of, list):
                        for item in any_of:
                            _push(item)
                    in_values = signal.get("in")
                    if isinstance(in_values, list):
                        for item in in_values:
                            _push(item)
                    _push(signal.get("equals"))
                    _push(signal.get("contains"))
            for child in node.values():
                _walk(child)
            return
        if isinstance(node, list):
            for child in node:
                _walk(child)

    _walk(conditions)
    return out


def _has_context_keyword_signal(conditions: Any) -> bool:
    if isinstance(conditions, dict):
        signal = conditions.get("signal")
        if isinstance(signal, dict):
            field_name = _fold_text(str(signal.get("field") or ""))
            if field_name == "context_keywords":
                return True
        return any(_has_context_keyword_signal(v) for v in conditions.values())
    if isinstance(conditions, list):
        return any(_has_context_keyword_signal(x) for x in conditions)
    return False


def _is_code_like_term(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return _CODE_LIKE_TOKEN_PATTERN.search(text) is not None


def _prompt_code_like_terms(prompt: str) -> set[str]:
    out: set[str] = set()
    raw = str(prompt or "")
    for m in _CODE_LIKE_TOKEN_PATTERN.finditer(raw):
        text = _fold_text(str(m.group(0) or ""))
        if text:
            out.add(text)
    for token in _extract_code_like_tokens(prompt, limit=8):
        text = _fold_text(token)
        if text:
            out.add(text)
    return out


def _strip_unprompted_code_like_terms(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
) -> tuple[RuleSuggestionDraftPayload, dict[str, Any]]:
    if _is_custom_secret_prompt(prompt):
        return draft, {"applied": False, "removed_terms": []}

    prompt_code_terms = _prompt_code_like_terms(prompt)
    removed_terms: list[str] = []

    def _is_unprompted_code_term(value: Any) -> bool:
        text = _fold_text(str(value or ""))
        if not text:
            return False
        if not _is_code_like_term(text):
            return False
        return text not in prompt_code_terms

    def _walk_and_strip(node: Any) -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {k: _walk_and_strip(v) for k, v in node.items()}
            signal = out.get("signal")
            if isinstance(signal, dict):
                field_name = _fold_text(str(signal.get("field") or ""))
                if field_name == "context_keywords":
                    for key in ("any_of", "in"):
                        values = signal.get(key)
                        if isinstance(values, list):
                            kept: list[Any] = []
                            for item in values:
                                if _is_unprompted_code_term(item):
                                    removed_terms.append(_fold_text(str(item or "")))
                                    continue
                                kept.append(item)
                            signal[key] = kept
                    for key in ("equals", "contains"):
                        value = signal.get(key)
                        if value is None:
                            continue
                        if _is_unprompted_code_term(value):
                            removed_terms.append(_fold_text(str(value or "")))
                            signal.pop(key, None)
            return out
        if isinstance(node, list):
            return [_walk_and_strip(x) for x in node]
        return node

    sanitized_conditions = _walk_and_strip(draft.rule.conditions)
    sanitized_terms: list[RuleSuggestionDraftContextTerm] = []
    for term in draft.context_terms:
        folded_term = _fold_text(term.term)
        if _is_unprompted_code_term(folded_term):
            removed_terms.append(folded_term)
            continue
        sanitized_terms.append(term)

    removed_terms = _to_str_list(removed_terms)
    if not removed_terms:
        return draft, {"applied": False, "removed_terms": []}

    sanitized_rule = draft.rule.model_copy(update={"conditions": sanitized_conditions})
    sanitized_draft = draft.model_copy(
        update={
            "rule": sanitized_rule,
            "context_terms": sanitized_terms,
        }
    )
    return sanitized_draft, {"applied": True, "removed_terms": removed_terms}


def _evaluate_runtime_usability(
    *,
    draft: RuleSuggestionDraftPayload,
    prompt: str | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    keyword_terms = _collect_context_keyword_terms(draft.rule.conditions)
    has_keyword_signal = _has_context_keyword_signal(draft.rule.conditions)
    if has_keyword_signal and not keyword_terms:
        warnings.append("context_keywords_signal_without_runtime_terms")
    if not keyword_terms and not warnings:
        return {"runtime_usable": True, "warnings": warnings, "abstract_terms": []}

    abstract_terms = [
        term for term in keyword_terms if term in _ABSTRACT_CONTEXT_KEYWORDS
    ]
    concrete_terms = [
        term for term in keyword_terms if term not in _ABSTRACT_CONTEXT_KEYWORDS
    ]
    code_terms = {
        _fold_text(term)
        for term in (
            keyword_terms + [str(t.term or "") for t in draft.context_terms]
        )
        if _is_code_like_term(str(term or ""))
    }
    prompt_code_terms = _prompt_code_like_terms(prompt or "")
    allow_unprompted_code_terms = prompt is None or _is_custom_secret_prompt(prompt or "")
    if (not allow_unprompted_code_terms) and code_terms:
        unexpected = sorted(code_terms - prompt_code_terms)
        if unexpected:
            warnings.append("unexpected_code_like_term_not_in_prompt")
        grounded_code_terms = sorted(code_terms & prompt_code_terms)
        has_code_anchor = bool(grounded_code_terms)
    else:
        has_code_anchor = bool(code_terms)

    if abstract_terms and (not concrete_terms) and (not has_code_anchor):
        warnings.append("abstract_context_keywords_not_runtime_usable")

    if ("exact" in abstract_terms) and (not has_code_anchor):
        warnings.append("context_keyword_exact_without_runtime_anchor")

    if ("token" in abstract_terms) and (not has_code_anchor):
        warnings.append("context_keyword_token_without_runtime_anchor")

    warnings = _to_str_list(warnings)
    return {
        "runtime_usable": not warnings,
        "warnings": warnings,
        "abstract_terms": _to_str_list(abstract_terms),
    }


def _apply_runtime_usability_constraint(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
) -> tuple[RuleSuggestionDraftPayload, dict[str, Any]]:
    meta = _evaluate_runtime_usability(draft=draft, prompt=prompt)
    warnings = _to_str_list(meta.get("warnings"))
    repaired = False
    repaired_reasons: list[str] = []
    guarded = draft

    if warnings and _is_custom_secret_prompt(prompt):
        tokens = _extract_code_like_tokens(prompt, limit=4)
        if tokens:
            h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
            guarded = _build_exact_secret_draft(
                prompt=prompt,
                token_terms=tokens,
                action=draft.rule.action,
                stable_suffix=h,
            )
            repaired = True
            repaired_reasons.append("runtime_usability_auto_repair_exact_secret")
            meta = _evaluate_runtime_usability(draft=guarded, prompt=prompt)
            warnings = _to_str_list(meta.get("warnings"))

    return guarded, {
        "runtime_usable": bool(meta.get("runtime_usable", not warnings)),
        "warnings": warnings,
        "repair_applied": repaired,
        "reasons": repaired_reasons,
        "abstract_terms": _to_str_list(meta.get("abstract_terms")),
    }


def _draft_has_exact_secret_terms(
    draft: RuleSuggestionDraftPayload, token_terms: list[str]
) -> bool:
    wanted = {str(x or "").strip().lower() for x in token_terms if str(x or "").strip()}
    if not wanted:
        return False

    # Custom-secret draft must encode token in runtime-usable rule condition.
    return any(_condition_has_context_keyword_term(draft.rule.conditions, x) for x in wanted)


def _post_generate_intent_guard(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
) -> tuple[RuleSuggestionDraftPayload, dict[str, Any]]:
    guarded = draft
    applied = False
    mismatch_detected = False
    reasons: list[str] = []
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]

    if _is_custom_secret_prompt(prompt):
        tokens = _extract_code_like_tokens(prompt, limit=4)
        if tokens:
            has_generic_pii = _contains_entity_type(
                guarded.rule.conditions,
                {"PHONE", "CCCD", "TAX_ID", "EMAIL", "CREDIT_CARD"},
            )
            has_exact_terms = _draft_has_exact_secret_terms(guarded, tokens)
            if has_generic_pii or (not has_exact_terms):
                mismatch_detected = True
                guarded = _build_exact_secret_draft(
                    prompt=prompt,
                    token_terms=tokens,
                    action=guarded.rule.action,
                    stable_suffix=h,
                )
                applied = True
                reasons.append("custom_secret_mismatch_auto_repair")

    if _is_payroll_external_email_prompt(prompt):
        has_payroll = (
            _condition_has_context_keyword_term(guarded.rule.conditions, "payroll")
            or _condition_has_context_keyword_term(guarded.rule.conditions, "salary")
            or _condition_has_context_keyword_term(guarded.rule.conditions, "luong")
        )
        has_external = (
            _condition_has_context_keyword_term(guarded.rule.conditions, "gmail")
            or _condition_has_context_keyword_term(
                guarded.rule.conditions, "personal email"
            )
            or _condition_has_context_keyword_term(
                guarded.rule.conditions, "external email"
            )
            or _condition_has_context_keyword_term(
                guarded.rule.conditions, "email ngoai cong ty"
            )
        )
        if (not has_payroll) or (not has_external):
            mismatch_detected = True
            guarded = _build_payroll_external_email_draft(
                prompt=prompt,
                action=guarded.rule.action,
                stable_suffix=h,
            )
            applied = True
            reasons.append("payroll_external_email_mismatch_auto_repair")

    grounded_draft, grounding_meta = _strip_unprompted_code_like_terms(
        prompt=prompt,
        draft=guarded,
    )
    if bool(grounding_meta.get("applied")):
        guarded = grounded_draft
        mismatch_detected = True
        applied = True
        reasons.append("removed_unprompted_code_like_terms")

    return guarded, {
        "applied": bool(applied),
        "mismatch_detected": bool(mismatch_detected),
        "reasons": reasons,
    }


def _build_persona_signal_draft(
    *,
    prompt: str,
    persona: str,
    keywords: list[str],
    action: RuleAction,
    stable_suffix: str,
) -> RuleSuggestionDraftPayload:
    stable_key = f"company.custom.suggested.{stable_suffix}"
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


def _fallback_generate(prompt: str) -> RuleSuggestionDraftPayload:
    p = prompt.lower()
    action = _action_hint_from_prompt(prompt)
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    code_tokens = _extract_code_like_tokens(prompt, limit=4)

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

    if _is_custom_secret_prompt(prompt) and code_tokens:
        return _build_exact_secret_draft(
            prompt=prompt,
            token_terms=code_tokens,
            action=action,
            stable_suffix=h,
        )

    if _is_payroll_external_email_prompt(prompt):
        return _build_payroll_external_email_draft(
            prompt=prompt,
            action=action,
            stable_suffix=h,
        )

    if _has_any(p, office_hr_keys):
        matched = [k for k in office_hr_keys if k in p][:4]
        return _build_persona_signal_draft(
            prompt=prompt,
            persona="office",
            keywords=matched or ["nhan su", "hop dong", "luong"],
            action=action,
            stable_suffix=h,
        )

    if _has_any(p, dev_infra_keys):
        matched = [k for k in dev_infra_keys if k in p][:4]
        return _build_persona_signal_draft(
            prompt=prompt,
            persona="dev",
            keywords=matched or ["docker", "kubernetes", "github"],
            action=action,
            stable_suffix=h,
        )

    if _is_finance_prompt(p) and (not _mentions_tax_id(p)):
        matched = [k for k in finance_keys if k in p][:4]
        return _build_persona_signal_draft(
            prompt=prompt,
            persona="finance",
            keywords=matched or ["bao cao tai chinh", "doanh thu", "loi nhuan"],
            action=action,
            stable_suffix=h,
        )

    if _has_any(p, ["cccd", "cmnd", "can cuoc", "căn cước"]):
        entity_type = "CCCD"
    elif _has_any(p, ["tax", "mst", "ma so thue", "mã số thuế"]):
        entity_type = "TAX_ID"
    elif _has_any(p, ["phone", "sdt", "so dien thoai", "số điện thoại", "hotline"]):
        entity_type = "PHONE"
    else:
        entity_type = "TAX_ID"

    stable_key = f"company.custom.suggested.{h}"
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key=stable_key,
            name=f"Suggested {entity_type} {action.value}",
            description=f"Auto-generated from prompt: {prompt[:180]}",
            scope=RuleScope.prompt,
            conditions={"any": [{"entity_type": entity_type}]},
            action=action,
            severity=RuleSeverity.medium,
            priority=120,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[],
    )


def _align_draft_with_prompt(
    prompt: str, draft: RuleSuggestionDraftPayload
) -> RuleSuggestionDraftPayload:
    p = prompt.lower()
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    code_tokens = _extract_code_like_tokens(prompt, limit=4)

    if _is_custom_secret_prompt(prompt) and code_tokens:
        # Keep custom-token intent; avoid drifting into common PII entity mapping.
        if _contains_entity_type(
            draft.rule.conditions,
            {"PHONE", "CCCD", "TAX_ID", "EMAIL", "CREDIT_CARD"},
        ) or (not _draft_has_exact_secret_terms(draft, code_tokens)):
            return _build_exact_secret_draft(
                prompt=prompt,
                token_terms=code_tokens,
                action=draft.rule.action,
                stable_suffix=h,
            )

    if _is_payroll_external_email_prompt(prompt):
        if (
            not _condition_has_context_keyword_term(draft.rule.conditions, "payroll")
            or not _condition_has_context_keyword_term(draft.rule.conditions, "gmail")
        ):
            return _build_payroll_external_email_draft(
                prompt=prompt,
                action=draft.rule.action,
                stable_suffix=h,
            )

    if _has_any(p, ["luong", "lương", "hop dong", "hợp đồng", "nhan su", "nhân sự", "hr"]):
        if _contains_entity_leaf(draft.rule.conditions):
            return _build_persona_signal_draft(
                prompt=prompt,
                persona="office",
                keywords=["nhan su", "hop dong", "luong"],
                action=draft.rule.action,
                stable_suffix=h,
            )

    if _has_any(p, ["docker", "kubernetes", "github", "helm", "devops"]):
        if _contains_entity_leaf(draft.rule.conditions):
            return _build_persona_signal_draft(
                prompt=prompt,
                persona="dev",
                keywords=["docker", "kubernetes", "github"],
                action=draft.rule.action,
                stable_suffix=h,
            )

    if _is_finance_prompt(p) and (not _mentions_tax_id(p)):
        if _contains_entity_leaf(draft.rule.conditions) or (
            not _has_signal_persona(draft.rule.conditions, "finance")
        ):
            return _build_persona_signal_draft(
                prompt=prompt,
                persona="finance",
                keywords=["bao cao tai chinh", "doanh thu", "loi nhuan"],
                action=draft.rule.action,
                stable_suffix=h,
            )

    return draft


def _enforce_prompt_semantic_guard(
    prompt: str, draft: RuleSuggestionDraftPayload
) -> RuleSuggestionDraftPayload:
    p = prompt.lower()
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    code_tokens = _extract_code_like_tokens(prompt, limit=4)

    if _is_custom_secret_prompt(prompt) and code_tokens:
        if _contains_entity_type(
            draft.rule.conditions,
            {"PHONE", "CCCD", "TAX_ID", "EMAIL", "CREDIT_CARD"},
        ) or (not _draft_has_exact_secret_terms(draft, code_tokens)):
            return _build_exact_secret_draft(
                prompt=prompt,
                token_terms=code_tokens,
                action=draft.rule.action,
                stable_suffix=h,
            )

    if _is_payroll_external_email_prompt(prompt):
        if (
            not _condition_has_context_keyword_term(draft.rule.conditions, "payroll")
            or not _condition_has_context_keyword_term(draft.rule.conditions, "gmail")
        ):
            return _build_payroll_external_email_draft(
                prompt=prompt,
                action=draft.rule.action,
                stable_suffix=h,
            )

    if (not _is_finance_prompt(p)) or _mentions_tax_id(p):
        return draft

    if _contains_entity_type(draft.rule.conditions, {"TAX_ID"}):
        return _build_persona_signal_draft(
            prompt=prompt,
            persona="finance",
            keywords=["bao cao tai chinh", "doanh thu", "loi nhuan"],
            action=draft.rule.action,
            stable_suffix=h,
        )

    if not _has_signal_persona(draft.rule.conditions, "finance"):
        return _build_persona_signal_draft(
            prompt=prompt,
            persona="finance",
            keywords=["bao cao tai chinh", "doanh thu", "loi nhuan"],
            action=draft.rule.action,
            stable_suffix=h,
        )

    return draft


def _tokenize_for_score(text: str) -> set[str]:
    parts = re.split(r"[^a-zA-Z0-9_]+", (text or "").lower())
    return {p for p in parts if p}


def _jaccard_score(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union <= 0:
        return 0.0
    return float(inter / union)


def _rule_reference_text(rule: Rule) -> str:
    return "\n".join(
        [
            f"stable_key: {rule.stable_key}",
            f"name: {rule.name}",
            f"description: {rule.description or ''}",
            f"scope: {rule.scope.value}",
            f"action: {rule.action.value}",
            f"severity: {rule.severity.value}",
            f"priority: {int(rule.priority)}",
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

    scored: list[tuple[float, int, Rule]] = []
    for row in rows:
        score = _jaccard_score(prompt_tokens, _tokenize_for_score(_rule_reference_text(row)))
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
                "rag_mode": row.rag_mode.value,
                "conditions": row.conditions,
                "origin": "global_default" if row.company_id is None else "company_rule",
                "prompt_overlap_score": round(float(score), 4),
            }
        )
    return out


def _run_coro_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("cannot_block_on_running_event_loop")


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
                embed_model=_SUGGESTION_POLICY_EMBED_MODEL,
                embedding_dim=_SUGGESTION_POLICY_EMBED_DIM,
                top_k=3,
            )
        except Exception:
            self.policy_retriever = None

    def retrieve_policy_chunks(
        self,
        prompt: str,
        user_id: UUID,
        top_k: int = 3,
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
            )
        except Exception:
            return []


def _ensure_company_stable_key(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
) -> RuleSuggestionDraftPayload:
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:10]
    stable_key = str(draft.rule.stable_key or "").strip().lower()
    stable_key = re.sub(r"[^a-z0-9._-]+", ".", stable_key)
    stable_key = re.sub(r"\.+", ".", stable_key).strip(".")

    if not stable_key or stable_key.startswith("global."):
        slug = ".".join(sorted(_tokenize_for_score(prompt)))[:60].strip(".")
        if not slug:
            slug = f"suggested.{h}"
        stable_key = f"company.custom.{slug}.{h}"
    elif not stable_key.startswith("company."):
        stable_key = f"company.custom.{stable_key}"

    stable_key = stable_key[:200].strip(".")
    if not stable_key:
        stable_key = f"company.custom.suggested.{h}"

    rule = draft.rule.model_copy(update={"stable_key": stable_key})
    return draft.model_copy(update={"rule": rule})


def _generate_with_llm(
    prompt: str,
    *,
    prompt_keywords: list[str],
    policy_chunks: list[dict[str, Any]],
    rule_references: list[dict[str, Any]],
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
    "conditions": {"all":[{"signal":{"field":"persona","equals":"dev|office"}}]} OR {"any":[{"entity_type":"PHONE|CCCD|TAX_ID|EMAIL|CREDIT_CARD|API_SECRET|INTERNAL_CODE|CUSTOM_SECRET"}]} OR {"all":[{"signal":{"field":"context_keywords","any_of":["<concrete_term_from_user_prompt>"]}}]},
    "action": "allow|mask|block",
    "severity": "low|medium|high",
    "priority": 0,
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

    keywords_json = json.dumps(prompt_keywords[:16], ensure_ascii=False)
    policy_json = json.dumps(policy_chunks[:5], ensure_ascii=False)
    references_json = json.dumps(rule_references[:8], ensure_ascii=False)
    prompt_input = (
        "User request:\n"
        f"{prompt}\n\n"
        "Detected request keywords:\n"
        f"{keywords_json}\n\n"
        "Relevant policy excerpts:\n"
        f"{policy_json}\n\n"
        "Related existing rules:\n"
        f"{references_json}\n\n"
        "Task / output schema requirements:\n"
        "1) Prefer rule conditions consistent with existing rule DSL.\n"
        "2) stable_key must be company-specific, never global.*.\n"
        "3) Use policy excerpts as grounding context when they are relevant.\n"
        "4) If related rule contains same policy intent, keep naming and conditions style close to that rule.\n"
        "5) Avoid generating redundant duplicate policy when related rules already cover it.\n"
        "6) If request mentions a specific internal code/token/secret that appears in the user request, prioritize exact-term protection and do not map to common PII entity types unless user explicitly asks.\n"
        "7) If request mentions payroll/salary plus personal/external email (e.g. gmail), draft conditions must reflect BOTH payroll domain and external-email risk, not generic office-only context.\n"
    )

    llm_out = generate_text_sync(
        prompt=prompt_input,
        system_prompt=system_prompt,
        provider=get_settings().non_embedding_llm_provider,
    )
    raw = llm_out.text
    obj = _parse_json_object(raw)
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
    normalized_prompt = _normalize_non_empty(value=prompt, field="prompt")
    prompt_keywords = sorted(_tokenize_for_score(normalized_prompt))[:16]
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
    )
    policy_chunk_ids = _to_str_list([x.get("chunk_id") for x in policy_chunks])
    related_rule_ids = _to_str_list([x.get("rule_id") for x in rule_references])
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
            prompt_keywords=prompt_keywords,
            policy_chunks=policy_chunks,
            rule_references=rule_references,
        )
        meta["context_retrieval"] = context_retrieval_meta
    except Exception:
        draft = _fallback_generate(normalized_prompt)
        meta = {
            "source": "fallback_generator",
            "provider": "none",
            "model": "none",
            "fallback_used": False,
            "context_retrieval": context_retrieval_meta,
        }

    draft = _ensure_company_stable_key(prompt=normalized_prompt, draft=draft)
    draft = _align_draft_with_prompt(normalized_prompt, draft)
    draft = _enforce_prompt_semantic_guard(normalized_prompt, draft)
    draft, intent_guard_meta = _post_generate_intent_guard(
        prompt=normalized_prompt,
        draft=draft,
    )
    draft, runtime_usability_meta = _apply_runtime_usability_constraint(
        prompt=normalized_prompt,
        draft=draft,
    )
    meta["intent_guard"] = intent_guard_meta
    meta["runtime_usability"] = runtime_usability_meta
    try:
        return _normalize_draft(draft), meta
    except Exception:
        # Last-resort fallback for malformed LLM draft.
        fb = _fallback_generate(normalized_prompt)
        fb = _ensure_company_stable_key(prompt=normalized_prompt, draft=fb)
        fb = _align_draft_with_prompt(normalized_prompt, fb)
        fb = _enforce_prompt_semantic_guard(normalized_prompt, fb)
        fb, fb_intent_guard_meta = _post_generate_intent_guard(
            prompt=normalized_prompt,
            draft=fb,
        )
        fb, fb_runtime_usability_meta = _apply_runtime_usability_constraint(
            prompt=normalized_prompt,
            draft=fb,
        )
        return _normalize_draft(fb), {
            "source": "fallback_generator_after_normalize_error",
            "provider": "none",
            "model": "none",
            "fallback_used": False,
            "context_retrieval": context_retrieval_meta,
            "intent_guard": fb_intent_guard_meta,
            "runtime_usability": fb_runtime_usability_meta,
        }


def _load_suggestion_or_404(
    *, session: Session, company_id: UUID, suggestion_id: UUID
) -> RuleSuggestion:
    row = session.get(RuleSuggestion, suggestion_id)
    if not row or row.company_id != company_id:
        raise not_found("Suggestion not found", field="suggestion_id")
    return _expire_if_needed(session=session, row=row)


def generate_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionGenerateIn,
) -> RuleSuggestionGenerateOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    draft, generation_meta = _generate_draft_from_prompt(
        session=session,
        company_id=company_id,
        actor_user_id=actor_user_id,
        prompt=payload.prompt,
    )
    duplicate_check = build_duplicate_check(
        session=session,
        company_id=company_id,
        draft_rule=draft.rule,
    )
    key = _dedupe_key(company_id=company_id, payload=draft)
    duplicate_meta = {
        "decision": duplicate_check.decision.value,
        "source": str(duplicate_check.source),
        "llm_provider": duplicate_check.llm_provider,
        "llm_model": duplicate_check.llm_model,
        "llm_fallback_used": bool(duplicate_check.llm_fallback_used),
        "rationale": str(duplicate_check.rationale),
        "confidence": float(duplicate_check.confidence),
    }

    existed = _find_active_duplicate(
        session=session,
        company_id=company_id,
        dedupe_key=key,
    )
    if existed:
        _append_log(
            session=session,
            suggestion_id=existed.id,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="suggestion.generate.duplicate_hit",
            reason="dedupe_key_matched_active_suggestion",
            before_json=None,
            after_json=_snapshot_suggestion(existed),
        )
        _append_log(
            session=session,
            suggestion_id=existed.id,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="suggestion.generate.telemetry",
            reason=(
                f"draft_source={generation_meta.get('source')} "
                f"draft_provider={generation_meta.get('provider')} "
                f"duplicate_source={duplicate_meta['source']} "
                f"duplicate_provider={duplicate_meta.get('llm_provider') or 'none'}"
            ),
            before_json=None,
            after_json={
                "draft_generation": generation_meta,
                "duplicate_check": duplicate_meta,
            },
        )
        session.commit()
        session.refresh(existed)
        existed_out = _to_out(existed)
        explanation = _build_suggestion_explanation(
            prompt=existed_out.nl_input,
            draft=existed_out.draft,
            duplicate_meta=duplicate_meta,
        )
        quality_signals = _build_quality_signals(
            prompt=existed_out.nl_input,
            draft=existed_out.draft,
            duplicate_meta=duplicate_meta,
            generation_meta=generation_meta,
        )
        retrieval_context = _build_retrieval_context(generation_meta=generation_meta)
        return RuleSuggestionGenerateOut(
            **existed_out.model_dump(),
            duplicate_check=duplicate_check,
            explanation=explanation,
            quality_signals=quality_signals,
            retrieval_context=retrieval_context,
        )

    row = RuleSuggestion(
        company_id=company_id,
        created_by=actor_user_id,
        status=SuggestionStatus.draft.value,
        type="rule_with_context",
        version=1,
        nl_input=_normalize_non_empty(value=payload.prompt, field="prompt"),
        draft_json=_draft_to_json(draft),
        dedupe_key=key,
        expires_at=_utcnow() + timedelta(days=SUGGESTION_TTL_DAYS),
    )
    session.add(row)
    session.flush()
    _append_log(
        session=session,
        suggestion_id=row.id,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="suggestion.create",
        before_json=None,
        after_json=_snapshot_suggestion(row),
    )
    _append_log(
        session=session,
        suggestion_id=row.id,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="suggestion.generate.telemetry",
        reason=(
            f"draft_source={generation_meta.get('source')} "
            f"draft_provider={generation_meta.get('provider')} "
            f"duplicate_source={duplicate_meta['source']} "
            f"duplicate_provider={duplicate_meta.get('llm_provider') or 'none'}"
        ),
        before_json=None,
        after_json={
            "draft_generation": generation_meta,
            "duplicate_check": duplicate_meta,
        },
    )
    session.commit()
    session.refresh(row)
    created_out = _to_out(row)
    explanation = _build_suggestion_explanation(
        prompt=created_out.nl_input,
        draft=created_out.draft,
        duplicate_meta=duplicate_meta,
    )
    quality_signals = _build_quality_signals(
        prompt=created_out.nl_input,
        draft=created_out.draft,
        duplicate_meta=duplicate_meta,
        generation_meta=generation_meta,
    )
    retrieval_context = _build_retrieval_context(generation_meta=generation_meta)
    return RuleSuggestionGenerateOut(
        **created_out.model_dump(),
        duplicate_check=duplicate_check,
        explanation=explanation,
        quality_signals=quality_signals,
        retrieval_context=retrieval_context,
    )


def list_rule_suggestions(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    status: SuggestionStatus | None,
    limit: int,
) -> list[RuleSuggestionOut]:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    safe_limit = max(1, min(int(limit), 200))
    stmt = (
        select(RuleSuggestion)
        .where(RuleSuggestion.company_id == company_id)
        .order_by(RuleSuggestion.created_at.desc())
        .limit(safe_limit)
    )
    if status is not None:
        stmt = stmt.where(RuleSuggestion.status == status.value)
    rows = list(session.exec(stmt).all())
    out: list[RuleSuggestionOut] = []
    for row in rows:
        row = _expire_if_needed(session=session, row=row)
        out.append(_to_out(row))
    return out


def get_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
) -> RuleSuggestionGetOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)
    row = _load_suggestion_or_404(
        session=session, company_id=company_id, suggestion_id=suggestion_id
    )
    out = _to_out(row)
    generation_meta, duplicate_meta = _load_generate_telemetry(
        session=session,
        suggestion_id=row.id,
    )
    explanation = _build_suggestion_explanation(
        prompt=out.nl_input,
        draft=out.draft,
        duplicate_meta=duplicate_meta,
    )
    quality_signals = _build_quality_signals(
        prompt=out.nl_input,
        draft=out.draft,
        duplicate_meta=duplicate_meta,
        generation_meta=generation_meta,
    )
    return RuleSuggestionGetOut(
        **out.model_dump(),
        explanation=explanation,
        quality_signals=quality_signals,
    )


def simulate_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionSimulateIn,
) -> RuleSuggestionSimulateOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    row = _load_suggestion_row_or_404(
        session=session,
        company_id=company_id,
        suggestion_id=suggestion_id,
    )
    effective_status = row.status
    if row.expires_at and row.expires_at <= _utcnow():
        effective_status = SuggestionStatus.expired.value

    if effective_status not in {SuggestionStatus.draft.value, SuggestionStatus.approved.value}:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Suggestion cannot be simulated in current status",
            details=[{"field": "status", "reason": "invalid_status_for_simulate"}],
        )

    draft = _normalize_draft(RuleSuggestionDraftPayload.model_validate(row.draft_json))
    runtime_rules = _build_simulation_runtime_rules(
        session=session,
        company_id=company_id,
        suggestion_id=row.id,
        draft_rule=draft.rule,
    )
    runtime_meta = _evaluate_runtime_usability(draft=draft, prompt=row.nl_input)
    runtime_warnings = _to_str_list(runtime_meta.get("warnings"))
    runtime_usable = bool(runtime_meta.get("runtime_usable", not runtime_warnings))
    if runtime_warnings:
        runtime_usable = False

    action_breakdown = {"ALLOW": 0, "MASK": 0, "BLOCK": 0}
    matched_count = 0
    results: list[RuleSuggestionSimulateResultOut] = []
    draft_stable_key = str(draft.rule.stable_key)
    draft_exact_terms = _collect_simulation_exact_terms_from_draft(draft=draft)
    overrides = load_context_runtime_overrides(
        session=session,
        company_id=company_id,
    )
    samples = [{"content": text} for text in payload.samples]

    for sample in samples:
        text = str(sample.get("content") or "").strip()
        if not text:
            continue

        entities = _SIMULATE_DETECTOR.scan(
            text,
            context_hints_by_entity=overrides.regex_hints,
        )
        ctx = _SIMULATE_CONTEXT_SCORER.score(
            text,
            persona_keywords_override=overrides.persona_keywords,
        )
        signals = _SIMULATE_CONTEXT_SCORER.to_signals_dict(ctx)
        matched_exact_terms = _match_simulation_exact_terms_in_text(
            text=text,
            exact_terms=draft_exact_terms,
        )
        signals["context_keywords"] = _merge_simulation_context_keywords(
            context_keywords=list(signals.get("context_keywords") or []),
            extra_keywords=matched_exact_terms,
        )
        matches = _evaluate_with_runtime_rules(
            runtime_rules=runtime_rules,
            entities=entities,
            signals=signals,
        )
        decision = _SIMULATE_RESOLVER.resolve(matches)

        action = _action_key(decision.final_action)
        action_breakdown[action] = int(action_breakdown.get(action, 0)) + 1

        affected_by_draft = any(str(m.stable_key) == draft_stable_key for m in matches)
        if affected_by_draft:
            matched_count += 1

        results.append(
            RuleSuggestionSimulateResultOut(
                content=text,
                matched=affected_by_draft,
                predicted_action=action,
            )
        )

    return RuleSuggestionSimulateOut(
        suggestion_id=row.id,
        sample_size=len(samples),
        runtime_usable=runtime_usable,
        runtime_warnings=runtime_warnings,
        matched_count=matched_count,
        action_breakdown=action_breakdown,
        results=results,
    )


def simulate_rule_suggestion_by_id(
    *,
    session: Session,
    suggestion_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionSimulateIn,
) -> RuleSuggestionSimulateOut:
    row = session.get(RuleSuggestion, suggestion_id)
    if not row:
        raise not_found("Suggestion not found", field="suggestion_id")
    if row.company_id is None:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Suggestion has invalid rule_set context",
            details=[{"field": "suggestion_id", "reason": "missing_rule_set"}],
        )

    return simulate_rule_suggestion(
        session=session,
        company_id=row.company_id,
        suggestion_id=suggestion_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )


def list_rule_suggestion_logs(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
    limit: int,
) -> list[RuleSuggestionLogOut]:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)
    _load_suggestion_or_404(session=session, company_id=company_id, suggestion_id=suggestion_id)

    safe_limit = max(1, min(int(limit), 200))
    rows = list(
        session.exec(
            select(RuleSuggestionLog)
            .where(RuleSuggestionLog.suggestion_id == suggestion_id)
            .order_by(RuleSuggestionLog.created_at.desc())
            .limit(safe_limit)
        ).all()
    )
    return [_to_log_out(r) for r in rows]


def edit_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionEditIn,
) -> RuleSuggestionOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    row = _load_suggestion_or_404(
        session=session, company_id=company_id, suggestion_id=suggestion_id
    )
    if row.status != SuggestionStatus.draft.value:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Only draft suggestion can be edited",
            details=[{"field": "status", "reason": "not_draft"}],
        )
    _assert_expected_version(
        current_version=int(row.version),
        expected_version=payload.expected_version,
    )

    normalized = _normalize_draft(payload.draft)
    key = _dedupe_key(company_id=company_id, payload=normalized)
    existed = _find_active_duplicate(
        session=session,
        company_id=company_id,
        dedupe_key=key,
        exclude_suggestion_id=row.id,
    )
    if existed:
        raise AppError.conflict(
            ErrorCode.CONFLICT,
            "Duplicate active suggestion exists",
            field="draft",
        )

    before_json = _snapshot_suggestion(row)
    row.draft_json = _draft_to_json(normalized)
    row.dedupe_key = key
    row.version = int(row.version) + 1
    session.add(row)
    _append_log(
        session=session,
        suggestion_id=row.id,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="suggestion.edit",
        before_json=before_json,
        after_json=_snapshot_suggestion(row),
    )
    session.commit()
    session.refresh(row)
    return _to_out(row)


def confirm_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionConfirmIn,
) -> RuleSuggestionOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)
    row = _load_suggestion_or_404(
        session=session, company_id=company_id, suggestion_id=suggestion_id
    )
    if row.status != SuggestionStatus.draft.value:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Only draft suggestion can be confirmed",
            details=[{"field": "status", "reason": "not_draft"}],
        )
    _assert_expected_version(
        current_version=int(row.version),
        expected_version=payload.expected_version,
    )

    draft = _normalize_draft(RuleSuggestionDraftPayload.model_validate(row.draft_json))
    duplicate_check = build_duplicate_check(
        session=session,
        company_id=company_id,
        draft_rule=draft.rule,
    )
    if (
        duplicate_check.decision == DuplicateDecision.exact_duplicate
        and duplicate_check.matched_rule_ids
        and duplicate_check.rationale != "stable_key_conflict"
    ):
        raise AppError(
            409,
            ErrorCode.CONFLICT,
            "Suggestion duplicates existing rule",
            details=[
                {
                    "field": "draft.rule",
                    "reason": "exact_duplicate_rule",
                    "extra": {
                        "matched_rule_ids": [str(x) for x in duplicate_check.matched_rule_ids],
                        "duplicate_rationale": duplicate_check.rationale,
                    },
                }
            ],
        )

    before_json = _snapshot_suggestion(row)
    row.status = SuggestionStatus.approved.value
    row.version = int(row.version) + 1
    row.approved_by = actor_user_id
    row.approved_at = _utcnow()
    row.approve_reason = (payload.reason or "").strip() or None
    session.add(row)
    _append_log(
        session=session,
        suggestion_id=row.id,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="suggestion.confirm",
        reason=row.approve_reason,
        before_json=before_json,
        after_json=_snapshot_suggestion(row),
    )
    session.commit()
    session.refresh(row)
    return _to_out(row)


def reject_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionRejectIn,
) -> RuleSuggestionOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)
    row = _load_suggestion_or_404(
        session=session, company_id=company_id, suggestion_id=suggestion_id
    )
    if row.status not in {SuggestionStatus.draft.value, SuggestionStatus.approved.value}:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Suggestion cannot be rejected in current status",
            details=[{"field": "status", "reason": "invalid_status"}],
        )
    _assert_expected_version(
        current_version=int(row.version),
        expected_version=payload.expected_version,
    )

    before_json = _snapshot_suggestion(row)
    row.status = SuggestionStatus.rejected.value
    row.version = int(row.version) + 1
    row.rejected_by = actor_user_id
    row.rejected_at = _utcnow()
    row.reject_reason = (payload.reason or "").strip() or None
    session.add(row)
    _append_log(
        session=session,
        suggestion_id=row.id,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="suggestion.reject",
        reason=row.reject_reason,
        before_json=before_json,
        after_json=_snapshot_suggestion(row),
    )
    session.commit()
    session.refresh(row)
    return _to_out(row)


def _apply_rule_draft(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    rule_draft: RuleSuggestionDraftRule,
) -> Rule:
    global_row = session.exec(
        select(Rule)
        .where(Rule.company_id.is_(None))
        .where(Rule.stable_key == rule_draft.stable_key)
    ).first()
    if global_row:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "stable_key is reserved by global rule",
            details=[{"field": "draft.rule.stable_key", "reason": "global_rule_key_reserved"}],
        )

    row = session.exec(
        select(Rule)
        .where(Rule.company_id == company_id)
        .where(Rule.stable_key == rule_draft.stable_key)
        .order_by(Rule.created_at.desc())
    ).first()
    if row is None:
        row = Rule(
            company_id=company_id,
            stable_key=rule_draft.stable_key,
            name=rule_draft.name,
            description=rule_draft.description,
            scope=rule_draft.scope,
            conditions=rule_draft.conditions,
            conditions_version=1,
            action=rule_draft.action,
            severity=rule_draft.severity,
            priority=rule_draft.priority,
            rag_mode=rule_draft.rag_mode,
            enabled=rule_draft.enabled,
            created_by=actor_user_id,
        )
        session.add(row)
        session.flush()
        return row

    row.name = rule_draft.name
    row.description = rule_draft.description
    row.scope = rule_draft.scope
    row.conditions = rule_draft.conditions
    row.conditions_version = int(row.conditions_version or 1) + 1
    row.action = rule_draft.action
    row.severity = rule_draft.severity
    row.priority = int(rule_draft.priority)
    row.rag_mode = rule_draft.rag_mode
    row.enabled = bool(rule_draft.enabled)
    session.add(row)
    session.flush()
    return row


def _apply_context_terms(
    *,
    session: Session,
    company_id: UUID,
    terms: list[RuleSuggestionDraftContextTerm],
) -> list[UUID]:
    out_ids: list[UUID] = []
    for t in terms:
        row = session.exec(
            select(ContextTerm)
            .where(ContextTerm.company_id == company_id)
            .where(ContextTerm.entity_type == t.entity_type)
            .where(ContextTerm.term == t.term)
            .where(ContextTerm.lang == t.lang)
            .order_by(ContextTerm.created_at.desc())
        ).first()
        if row is None:
            row = ContextTerm(
                company_id=company_id,
                entity_type=t.entity_type,
                term=t.term,
                lang=t.lang,
                weight=t.weight,
                window_1=t.window_1,
                window_2=t.window_2,
                enabled=t.enabled,
            )
        else:
            row.weight = t.weight
            row.window_1 = t.window_1
            row.window_2 = t.window_2
            row.enabled = t.enabled

        session.add(row)
        session.flush()
        out_ids.append(row.id)
    return out_ids


def apply_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionApplyIn | None = None,
) -> RuleSuggestionApplyOut:
    payload = payload or RuleSuggestionApplyIn()
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)
    row = _load_suggestion_or_404(
        session=session, company_id=company_id, suggestion_id=suggestion_id
    )
    _assert_expected_version(
        current_version=int(row.version),
        expected_version=payload.expected_version,
    )
    if row.status == SuggestionStatus.applied.value:
        result = row.applied_result_json or {}
        rule_id = str(result.get("rule_id") or "").strip()
        if not rule_id:
            raise AppError(
                409,
                ErrorCode.CONFLICT,
                "Suggestion was marked applied without result payload",
                details=[{"field": "applied_result_json", "reason": "missing_rule_id"}],
            )
        return RuleSuggestionApplyOut(
            rule_id=UUID(rule_id),
            context_term_ids=[UUID(str(x)) for x in list(result.get("context_term_ids") or [])],
        )
    if row.status != SuggestionStatus.approved.value:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Only approved suggestion can be applied",
            details=[{"field": "status", "reason": "not_approved"}],
        )

    draft = _normalize_draft(RuleSuggestionDraftPayload.model_validate(row.draft_json))
    before_json = _snapshot_suggestion(row)

    try:
        rule_row = _apply_rule_draft(
            session=session,
            company_id=company_id,
            actor_user_id=actor_user_id,
            rule_draft=draft.rule,
        )
        context_term_ids = _apply_context_terms(
            session=session,
            company_id=company_id,
            terms=draft.context_terms,
        )
        row.status = SuggestionStatus.applied.value
        row.version = int(row.version) + 1
        row.applied_by = actor_user_id
        row.applied_at = _utcnow()
        row.applied_result_json = {
            "rule_id": str(rule_row.id),
            "context_term_ids": [str(x) for x in context_term_ids],
        }
        session.add(row)
        _append_log(
            session=session,
            suggestion_id=row.id,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="suggestion.apply",
            before_json=before_json,
            after_json=_snapshot_suggestion(row),
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return RuleSuggestionApplyOut(
        rule_id=rule_row.id,
        context_term_ids=context_term_ids,
    )

