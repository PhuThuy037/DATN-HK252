from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.common.enums import MatchMode, RagMode, RuleAction, RuleScope, RuleSeverity
from app.suggestion.literal_detector import score_identifier_token
from app.suggestion.runtime_usability import (
    ABSTRACT_CONTEXT_KEYWORDS,
    collect_context_keyword_terms as collect_runtime_context_keyword_terms,
    evaluate_runtime_usability as evaluate_draft_runtime_usability,
    has_context_keyword_signal as has_runtime_context_keyword_signal,
    is_code_like_term as runtime_is_code_like_term,
    prompt_code_like_terms as runtime_prompt_code_like_terms,
)
from app.suggestion.schemas import (
    RuleSuggestionDraftContextTerm,
    RuleSuggestionDraftPayload,
    RuleSuggestionDraftRule,
)
from app.suggestion.suggestion_extractor import (
    PromptKeywordBundle,
    _GENERIC_MODIFIER_PHRASES,
    _PROMPT_GROUNDING_STOPWORDS,
    _extract_business_noun_phrases,
    _extract_prompt_context_phrases,
    _extract_target_phrases,
    _is_generic_modifier_phrase,
    _normalize_phrase_text,
    _remove_redundant_subphrases,
    _trim_context_phrase_against_keywords,
    _unique_phrase_values,
)
from app.suggestion.suggestion_generation import (
    _build_exact_secret_draft,
    _build_generic_prompt_keyword_draft,
    _build_payroll_external_email_draft,
    _build_persona_signal_draft,
    _build_literal_refinement_draft,
    _build_minimal_safe_prompt_draft,
    _tokenize_for_score,
)


def _svc() -> Any:
    from app.suggestion import service

    return service


def _fold_text(value: str) -> str:
    return _svc()._fold_text(value)


_PRIMARY_KEYWORD_TRAILING_NOISE_TOKENS = {
    "cac",
    "cho",
    "cua",
    "den",
    "dung",
    "hoi",
    "lam",
    "lien",
    "ngu",
    "nhu",
    "noi",
    "quan",
    "thong",
    "tin",
    "ve",
    "viec",
    "xau",
}


def _contains_prompt_keyword(*, folded_prompt: str, keyword: str) -> bool:
    return _svc()._contains_prompt_keyword(folded_prompt=folded_prompt, keyword=keyword)


def _normalize_lang(value: str) -> str:
    return _svc()._normalize_lang(value)


def _normalize_conditions_node(value: Any, *, field: str) -> Any:
    return _svc()._normalize_conditions_node(value, field=field)


def _normalize_term(value: str) -> str:
    return _svc()._normalize_term(value)


def _split_entity_types(*, raw_value: str, field: str) -> list[str]:
    return _svc()._split_entity_types(raw_value=raw_value, field=field)


def _normalize_stable_key(value: str) -> str:
    return _svc()._normalize_stable_key(value)


def _normalize_non_empty(*, value: str | None, field: str) -> str:
    return _svc()._normalize_non_empty(value=value, field=field)


def _has_any(text: str, keys: list[str]) -> bool:
    return _svc()._has_any(text, keys)


def _is_custom_secret_prompt(prompt: str) -> bool:
    return _svc()._is_custom_secret_prompt(prompt)


def _is_literal_secret_prompt(prompt: str) -> bool:
    return _svc()._is_literal_secret_prompt(prompt)


def _has_known_pii_intent(prompt: str) -> bool:
    return _svc()._has_known_pii_intent(prompt)


def _is_payroll_external_email_prompt(prompt: str) -> bool:
    return _svc()._is_payroll_external_email_prompt(prompt)


def _is_finance_prompt(prompt: str) -> bool:
    return _svc()._is_finance_prompt(prompt)


def _mentions_tax_id(prompt: str) -> bool:
    return _svc()._mentions_tax_id(prompt)


def _contains_entity_type(conditions: Any, wanted: set[str]) -> bool:
    return _svc()._contains_entity_type(conditions, wanted)


def _contains_entity_leaf(conditions: Any) -> bool:
    return _svc()._contains_entity_leaf(conditions)


def _has_signal_persona(conditions: Any, persona: str) -> bool:
    return _svc()._has_signal_persona(conditions, persona)


def _extract_code_like_tokens(prompt: str, *, limit: int = 6) -> list[str]:
    return _svc()._extract_code_like_tokens(prompt, limit=limit)


def _literal_detection(prompt: str, *, limit: int = 6) -> Any:
    return _svc()._literal_detection(prompt, limit=limit)


def _explicit_action_intent_from_prompt(prompt: str) -> RuleAction | None:
    return _svc()._explicit_action_intent_from_prompt(prompt)


def _extract_entity_types(node: Any) -> list[str]:
    return _svc()._extract_entity_types(node)


def _extract_persona_hint(node: Any) -> str | None:
    return _svc()._extract_persona_hint(node)


def _to_str_list(value: Any) -> list[str]:
    return _svc()._to_str_list(value)


def _prompt_keywords(prompt: str, *, limit: int = 6) -> PromptKeywordBundle:
    return _svc()._prompt_keywords(prompt, limit=limit)


def _drop_entity_type_from_conditions(
    conditions: Any,
    *,
    blocked_entity_types: set[str],
) -> tuple[Any | None, bool]:
    return _svc()._drop_entity_type_from_conditions(
        conditions,
        blocked_entity_types=blocked_entity_types,
    )


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


def _is_simple_builder_compatible_condition_node(node: Any) -> bool:
    if not isinstance(node, dict):
        return False

    if "entity_type" in node:
        raw = str(node.get("entity_type") or "").strip()
        if not raw:
            return False
        allowed_keys = {"entity_type", "min_score"}
        if any(key not in allowed_keys for key in node.keys()):
            return False
        if "min_score" in node:
            try:
                score = float(node["min_score"])
            except (TypeError, ValueError):
                return False
            if score < 0.0 or score > 1.0:
                return False
        return True

    signal = node.get("signal")
    if not isinstance(signal, dict):
        return False
    if str(signal.get("field") or "").strip() != "context_keywords":
        return False
    any_of = signal.get("any_of")
    if not isinstance(any_of, list) or len(any_of) == 0:
        return False
    values = [str(value or "").strip() for value in any_of]
    if any(not value for value in values):
        return False
    return set(signal.keys()) == {"field", "any_of"}


def _is_simple_builder_compatible_conditions(conditions: Any) -> bool:
    if not isinstance(conditions, dict):
        return False
    if set(conditions.keys()) != {"all"}:
        return False
    rows = conditions.get("all")
    if not isinstance(rows, list) or len(rows) == 0:
        return False
    return all(_is_simple_builder_compatible_condition_node(row) for row in rows)


def _normalize_to_simple_builder_conditions(
    *,
    conditions: Any,
    context_terms: list[RuleSuggestionDraftContextTerm],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen_entities: set[tuple[str, float | None]] = set()
    seen_signals: set[tuple[str, ...]] = set()

    def _add_entity_row(raw_node: dict[str, Any]) -> None:
        entity_type = str(raw_node.get("entity_type") or "").strip().upper()
        if not entity_type:
            return
        min_score: float | None = None
        if "min_score" in raw_node:
            try:
                parsed = float(raw_node["min_score"])
                if 0.0 <= parsed <= 1.0:
                    min_score = parsed
            except (TypeError, ValueError):
                min_score = None
        key = (entity_type, min_score)
        if key in seen_entities:
            return
        seen_entities.add(key)
        row: dict[str, Any] = {"entity_type": entity_type}
        if min_score is not None:
            row["min_score"] = min_score
        rows.append(row)

    def _add_signal_row(values: list[str]) -> None:
        cleaned = _sanitize_context_keyword_values(
            [str(value or "") for value in values],
            fallback_phrases=[str(value or "") for value in values],
        )
        if not cleaned:
            return
        dedupe_key = tuple(cleaned)
        if dedupe_key in seen_signals:
            return
        seen_signals.add(dedupe_key)
        rows.append(
            {
                "signal": {
                    "field": "context_keywords",
                    "any_of": cleaned,
                }
            }
        )

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if "entity_type" in node:
                _add_entity_row(node)
            if "signal" in node and isinstance(node.get("signal"), dict):
                signal = node["signal"]
                if str(signal.get("field") or "").strip() == "context_keywords":
                    signal_values: list[str] = []
                    raw_any_of = signal.get("any_of")
                    if isinstance(raw_any_of, list):
                        signal_values.extend(str(value or "") for value in raw_any_of)
                    raw_in = signal.get("in")
                    if isinstance(raw_in, list):
                        signal_values.extend(str(value or "") for value in raw_in)
                    for scalar_op in ("equals", "contains"):
                        scalar_value = signal.get(scalar_op)
                        if scalar_value is None:
                            continue
                        signal_values.append(str(scalar_value or ""))
                    _add_signal_row(signal_values)
            for key, child in node.items():
                # `not` cannot be represented in simple builder safely.
                if key == "not":
                    continue
                _walk(child)
            return
        if isinstance(node, list):
            for child in node:
                _walk(child)

    _walk(conditions)

    if not rows:
        fallback_terms = [str(term.term or "") for term in list(context_terms or [])]
        fallback_keywords = _sanitize_context_keyword_values(
            fallback_terms,
            fallback_phrases=fallback_terms,
        )
        if fallback_keywords:
            _add_signal_row(fallback_keywords)

    if not rows:
        rows.append({"signal": {"field": "context_keywords", "any_of": ["context"]}})

    return {"all": rows}


def _finalize_match_mode_from_context_terms(
    context_terms: list[RuleSuggestionDraftContextTerm],
) -> MatchMode:
    has_enabled_context_terms = any(
        bool(getattr(term, "enabled", True))
        and bool(str(getattr(term, "term", "") or "").strip())
        for term in list(context_terms or [])
    )
    if has_enabled_context_terms:
        return MatchMode.keyword_plus_semantic
    return MatchMode.strict_keyword


def _normalize_draft(payload: RuleSuggestionDraftPayload) -> RuleSuggestionDraftPayload:
    rule = payload.rule
    normalized_conditions = _normalize_conditions_node(
        rule.conditions,
        field="draft.rule.conditions",
    )
    action = RuleAction.mask if rule.action == RuleAction.warn else rule.action

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

    if not _is_simple_builder_compatible_conditions(normalized_conditions):
        normalized_conditions = _normalize_to_simple_builder_conditions(
            conditions=normalized_conditions,
            context_terms=normalized_terms,
        )

    normalized_rule = RuleSuggestionDraftRule(
        stable_key=_normalize_stable_key(rule.stable_key),
        name=_normalize_non_empty(value=rule.name, field="name"),
        description=(rule.description or "").strip() or None,
        scope=rule.scope,
        conditions=normalized_conditions,
        action=action,
        severity=rule.severity,
        priority=int(rule.priority),
        match_mode=_finalize_match_mode_from_context_terms(normalized_terms),
        rag_mode=rule.rag_mode,
        enabled=bool(rule.enabled),
    )

    return RuleSuggestionDraftPayload(rule=normalized_rule, context_terms=normalized_terms)

_CONTEXT_KEYWORD_NOISE_STOPWORDS = {
    "toi",
    "muon",
    "thong",
    "tin",
    "noi",
    "dung",
    "ve",
    "xau",
    "la",
    "gi",
}

_CONTEXT_KEYWORD_CONNECTOR_PHRASES = (
    "lien quan den",
    "lien quan",
    "thong tin ve",
    "cac noi dung ve",
    "nhung noi dung ve",
    "cac noi dung",
    "nhung noi dung",
    "thong tin",
    "noi dung",
    "cua",
    "ve",
    "hoi",
    "den",
    "cac",
    "nhung",
)

_CONTEXT_KEYWORD_CONNECTOR_WORDS = {
    "bo",
    "cua",
    "ve",
    "lien",
    "quan",
    "den",
    "cac",
    "nhung",
    "noi",
    "dung",
    "thong",
    "tin",
    "hoi",
}

_ENTITY_LIKE_TAIL_PATTERN = re.compile(
    r"(?<![a-z0-9])("
    r"(?:cong\s+ty|tap\s+doan|bo\s+phan|phong\s+ban|phong|trung\s+tam|chi\s+nhanh|"
    r"du\s+an|truong\s+nhom|can\s+bo|quan\s+ly|co\s+van|giang\s+vien|tro\s+giang|"
    r"to\s+chuc|ong|ba)"
    r"\s+[a-z0-9_.-]+(?:\s+[a-z0-9_.-]+){0,4}"
    r")$",
    re.IGNORECASE,
)

_CONTEXT_KEYWORD_BANNED_VALUES = {
    "literal refine required",
}

_DRAFT_DEBUG_BANNED_TEXTS = {
    "prompt keyword refinement",
    "cannot generate from this prompt yet",
    "literal refine required",
}

_CONTEXT_TERM_BOILERPLATE_PREFIXES = (
    "thong tin ve",
    "cac noi dung ve",
    "nhung noi dung ve",
    "lien quan den",
    "hoi ve",
)

_CONTEXT_TERM_TRAILING_CONNECTORS = (
    "cua",
)

_CONTEXT_TERM_EXACT_NOISE = {
    "thong tin",
    "thong tin ve",
    "lien quan den",
    "cac noi dung",
    "hoi ve",
}

_PROTECTED_CONTEXT_TERMS = {
    "noi xau",
    "boi nho",
    "noi bo",
    "tai lieu",
    "ke hoach mo rong thi truong",
    "quy trinh xu ly su co",
    "bao cao loi nhuan quy",
    "bao cao tai chinh",
    "tai lieu noi bo",
    "thong tin mat",
}

_GENERIC_ENTITY_NOUN_CONTEXT_TERMS = {
    "phong",
    "bo phan",
    "cong ty",
    "du an",
    "trung tam",
    "nhan vien",
}


def _is_entity_like_keyword_phrase(value: str) -> bool:
    normalized = _normalize_phrase_text(value)
    folded = _fold_text(normalized)
    if not folded:
        return False
    extracted = [_fold_text(item) for item in _extract_target_phrases(normalized, limit=4)]
    return folded in extracted


def _embedded_entity_keyword_phrase(value: str) -> str:
    normalized = _normalize_phrase_text(value)
    folded = _fold_text(normalized)
    if not folded:
        return ""
    extracted = [_fold_text(item) for item in _extract_target_phrases(normalized, limit=4)]
    for item in extracted:
        if item and item in folded:
            return _normalize_phrase_text(item)
    match = _ENTITY_LIKE_TAIL_PATTERN.search(folded)
    if match is not None:
        return _normalize_phrase_text(str(match.group(1) or ""))
    return ""


def _trim_connector_phrases(value: str) -> str:
    normalized = _normalize_phrase_text(value)
    if not normalized:
        return ""
    if _is_entity_like_keyword_phrase(normalized):
        return normalized
    embedded_entity = _embedded_entity_keyword_phrase(normalized)
    if embedded_entity:
        return embedded_entity

    trimmed = _fold_text(normalized)
    while trimmed:
        updated = trimmed
        for phrase in _CONTEXT_KEYWORD_CONNECTOR_PHRASES:
            pattern = re.compile(rf"^(?:{re.escape(phrase)})(?:\s+|$)", re.IGNORECASE)
            candidate = _normalize_phrase_text(pattern.sub("", trimmed, count=1))
            if candidate and candidate != trimmed:
                updated = candidate
                break
        if updated == trimmed:
            break
        embedded_entity = _embedded_entity_keyword_phrase(updated)
        if embedded_entity:
            return embedded_entity
        if _is_entity_like_keyword_phrase(updated):
            return updated
        trimmed = updated

    while trimmed:
        updated = trimmed
        for phrase in _CONTEXT_KEYWORD_CONNECTOR_PHRASES:
            pattern = re.compile(rf"(?:^|\s+)(?:{re.escape(phrase)})$", re.IGNORECASE)
            candidate = _normalize_phrase_text(pattern.sub("", trimmed, count=1))
            if candidate and candidate != trimmed:
                updated = candidate
                break
        if updated == trimmed:
            break
        embedded_entity = _embedded_entity_keyword_phrase(updated)
        if embedded_entity:
            return embedded_entity
        if _is_entity_like_keyword_phrase(updated):
            return updated
        trimmed = updated

    return _normalize_phrase_text(trimmed)


def _is_connector_only_keyword_phrase(value: str) -> bool:
    folded = _fold_text(value)
    if not folded:
        return True
    tokens = [token for token in re.split(r"[^a-zA-Z0-9_]+", folded) if token]
    if not tokens:
        return True
    if len(tokens) <= 2 and all(token in _CONTEXT_KEYWORD_CONNECTOR_WORDS for token in tokens):
        return True
    if all(token in _CONTEXT_KEYWORD_CONNECTOR_WORDS for token in tokens):
        return True
    return False


def _trim_context_term_boilerplate(value: str) -> str:
    normalized = _normalize_phrase_text(value)
    folded = _fold_text(normalized)
    if not folded:
        return ""
    if folded in _PROTECTED_CONTEXT_TERMS:
        return normalized

    trimmed = folded
    while trimmed:
        updated = trimmed
        for prefix in _CONTEXT_TERM_BOILERPLATE_PREFIXES:
            pattern = re.compile(rf"^(?:{re.escape(prefix)})(?:\s+|$)", re.IGNORECASE)
            candidate = _normalize_phrase_text(pattern.sub("", trimmed, count=1))
            if candidate and candidate != trimmed:
                updated = candidate
                break
        if updated == trimmed:
            break
        if updated in _PROTECTED_CONTEXT_TERMS:
            return updated
        trimmed = updated

    while trimmed:
        updated = trimmed
        for suffix in _CONTEXT_TERM_TRAILING_CONNECTORS:
            pattern = re.compile(rf"(?:^|\s+)(?:{re.escape(suffix)})$", re.IGNORECASE)
            candidate = _normalize_phrase_text(pattern.sub("", trimmed, count=1))
            if candidate and candidate != trimmed:
                updated = candidate
                break
        if updated == trimmed:
            break
        if updated in _PROTECTED_CONTEXT_TERMS:
            return updated
        trimmed = updated

    return _normalize_phrase_text(trimmed)


def _is_meaningful_context_term(value: str) -> bool:
    folded = _fold_text(value)
    if not folded:
        return False
    if folded in _PROTECTED_CONTEXT_TERMS:
        return True
    if folded in _GENERIC_ENTITY_NOUN_CONTEXT_TERMS:
        return False
    if _is_connector_only_keyword_phrase(folded):
        return False
    content_tokens = [
        token for token in re.split(r"[^a-zA-Z0-9_]+", folded) if token and token not in _CONTEXT_KEYWORD_CONNECTOR_WORDS
    ]
    if not content_tokens:
        return False
    if len(content_tokens) == 1 and len(content_tokens[0]) <= 3:
        return False
    return True


def _embedded_protected_context_term(value: str) -> str:
    folded = _fold_text(value)
    if not folded:
        return ""
    for phrase in sorted(_PROTECTED_CONTEXT_TERMS, key=len, reverse=True):
        if phrase in folded:
            return phrase
    return ""


def _sanitize_context_term_values(
    values: list[Any],
    *,
    keyword_phrases: list[str],
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    keyword_folds = {_fold_text(value) for value in keyword_phrases if _fold_text(value)}

    for raw_value in values:
        text = _normalize_phrase_text(str(raw_value or ""))
        if not text:
            continue
        text = _trim_context_phrase_against_keywords(text, keyword_phrases)
        text = _trim_context_term_boilerplate(text)
        folded = _fold_text(text)
        if not folded:
            continue
        token_count = len([token for token in re.split(r"[^a-zA-Z0-9_]+", folded) if token])
        if folded in _CONTEXT_TERM_EXACT_NOISE:
            continue
        if token_count <= 2 and folded in _GENERIC_ENTITY_NOUN_CONTEXT_TERMS:
            continue
        if folded in keyword_folds:
            continue
        if any(
            folded != keyword_fold
            and len(folded) < len(keyword_fold)
            and folded in keyword_fold
            and token_count <= 2
            for keyword_fold in keyword_folds
        ):
            continue
        if not _is_meaningful_context_term(text):
            continue
        if folded in seen:
            continue
        seen.add(folded)
        out.append(text)
    return out

def _sanitize_context_keyword_values(
    values: list[Any],
    *,
    fallback_phrases: list[str],
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def _append_if_valid(raw_value: Any) -> None:
        text = _normalize_phrase_text(str(raw_value or ""))
        if not text:
            return
        folded = _fold_text(text)
        if not folded:
            return
        if folded in _CONTEXT_KEYWORD_BANNED_VALUES:
            return
        if _is_connector_only_keyword_phrase(text):
            return
        is_single_token = " " not in folded
        if is_single_token:
            if folded in _CONTEXT_KEYWORD_NOISE_STOPWORDS:
                return
            if len(folded) <= 3:
                return
        if folded in seen:
            return
        seen.add(folded)
        out.append(text)

    for value in values:
        _append_if_valid(value)

    if out:
        return out

    for phrase in fallback_phrases:
        _append_if_valid(phrase)
    if out:
        return out

    for value in values:
        text = _normalize_phrase_text(str(value or ""))
        if not text:
            continue
        folded = _fold_text(text)
        if folded in _CONTEXT_KEYWORD_BANNED_VALUES:
            continue
        if not folded or folded in seen:
            continue
        seen.add(folded)
        out.append(text)
        if len(out) >= 1:
            break
    return out

def _sanitize_context_keyword_conditions(
    node: Any,
    *,
    fallback_phrases: list[str],
) -> Any:
    if isinstance(node, dict):
        out: dict[str, Any] = {
            key: _sanitize_context_keyword_conditions(value, fallback_phrases=fallback_phrases)
            for key, value in node.items()
        }
        signal = out.get("signal")
        if isinstance(signal, dict):
            field_name = _fold_text(str(signal.get("field") or ""))
            if field_name == "context_keywords":
                for list_op in ("any_of", "in"):
                    raw_values = signal.get(list_op)
                    if isinstance(raw_values, list):
                        sanitized_values = _sanitize_context_keyword_values(
                            raw_values,
                            fallback_phrases=fallback_phrases,
                        )
                        if sanitized_values:
                            signal[list_op] = sanitized_values
                        else:
                            signal.pop(list_op, None)
                for scalar_op in ("equals", "contains"):
                    raw_value = signal.get(scalar_op)
                    if raw_value is None:
                        continue
                    sanitized = _sanitize_context_keyword_values(
                        [raw_value],
                        fallback_phrases=fallback_phrases,
                    )
                    if sanitized:
                        signal[scalar_op] = sanitized[0]
                    else:
                        signal.pop(scalar_op, None)

                ops = [k for k in SIGNAL_OPERATOR_KEYS if k in signal]
                if not ops:
                    fallback_values = _sanitize_context_keyword_values(
                        list(fallback_phrases),
                        fallback_phrases=fallback_phrases,
                    )
                    if fallback_values:
                        signal["any_of"] = fallback_values
        return out
    if isinstance(node, list):
        return [
            _sanitize_context_keyword_conditions(value, fallback_phrases=fallback_phrases)
            for value in node
        ]
    return node

def _sanitize_draft_context_keywords(
    *,
    draft: RuleSuggestionDraftPayload,
    prompt_keyword_bundle: PromptKeywordBundle,
) -> RuleSuggestionDraftPayload:
    sanitized_conditions = _sanitize_context_keyword_conditions(
        draft.rule.conditions,
        fallback_phrases=list(prompt_keyword_bundle.get("phrases") or []),
    )
    sanitized_rule = draft.rule.model_copy(update={"conditions": sanitized_conditions})
    return draft.model_copy(update={"rule": sanitized_rule})

def _prompt_grounding_term_set(
    prompt: str,
    *,
    prompt_keyword_bundle: PromptKeywordBundle,
) -> set[str]:
    out: set[str] = set()
    for phrase in list(prompt_keyword_bundle.get("phrases") or []):
        folded = _fold_text(phrase)
        if folded:
            out.add(folded)
    for phrase in _extract_target_phrases(prompt, limit=12):
        folded = _fold_text(phrase)
        if folded:
            out.add(folded)
    for phrase in _extract_prompt_context_phrases(prompt, limit=12):
        folded = _fold_text(phrase)
        if folded:
            out.add(folded)
    return out

def _term_is_prompt_grounded(
    term: Any,
    *,
    folded_prompt: str,
    prompt_tokens: set[str],
    grounding_terms: set[str],
) -> bool:
    folded = _fold_text(str(term or ""))
    if not folded:
        return False
    if folded in _CONTEXT_KEYWORD_BANNED_VALUES:
        return False
    if folded in grounding_terms:
        return True
    if _contains_prompt_keyword(folded_prompt=folded_prompt, keyword=folded):
        return True

    term_tokens = [p for p in re.split(r"[^a-zA-Z0-9_]+", folded) if p]
    content_tokens = [t for t in term_tokens if t not in _PROMPT_GROUNDING_STOPWORDS]
    if not content_tokens:
        return False
    if len(content_tokens) == 1:
        token = content_tokens[0]
        return (len(token) >= 4) and (token in prompt_tokens)

    overlap = [t for t in content_tokens if t in prompt_tokens]
    if not overlap:
        return False
    return (len(overlap) / max(1, len(content_tokens))) >= 0.6

def _filter_and_ground_context_terms(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
    prompt_keyword_bundle: PromptKeywordBundle,
) -> RuleSuggestionDraftPayload:
    folded_prompt = _fold_text(prompt)
    prompt_tokens = {
        token
        for token in re.split(r"[^a-zA-Z0-9_]+", folded_prompt)
        if token and token not in _PROMPT_GROUNDING_STOPWORDS
    }
    grounding_terms = _prompt_grounding_term_set(
        prompt,
        prompt_keyword_bundle=prompt_keyword_bundle,
    )
    keyword_phrases = _sanitize_context_keyword_values(
        _collect_context_keyword_terms(draft.rule.conditions),
        fallback_phrases=list(prompt_keyword_bundle.get("phrases") or []),
    )

    context_fallback_phrases = _extract_prompt_context_phrases(prompt, limit=8)
    condition_fallback = list(prompt_keyword_bundle.get("phrases") or []) or context_fallback_phrases

    def _filter_condition_keywords(node: Any) -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {
                key: _filter_condition_keywords(value) for key, value in node.items()
            }
            signal = out.get("signal")
            if isinstance(signal, dict):
                field_name = _fold_text(str(signal.get("field") or ""))
                if field_name == "context_keywords":
                    for op in ("any_of", "in"):
                        values = signal.get(op)
                        if isinstance(values, list):
                            kept = [
                                value
                                for value in values
                                if _term_is_prompt_grounded(
                                    value,
                                    folded_prompt=folded_prompt,
                                    prompt_tokens=prompt_tokens,
                                    grounding_terms=grounding_terms,
                                )
                            ]
                            if kept:
                                signal[op] = kept
                            else:
                                signal.pop(op, None)
                    for op in ("equals", "contains"):
                        value = signal.get(op)
                        if value is None:
                            continue
                        if _term_is_prompt_grounded(
                            value,
                            folded_prompt=folded_prompt,
                            prompt_tokens=prompt_tokens,
                            grounding_terms=grounding_terms,
                        ):
                            continue
                        signal.pop(op, None)

                    current_values = _collect_context_keyword_terms({"signal": signal})
                    if not current_values and condition_fallback:
                        signal["any_of"] = _sanitize_context_keyword_values(
                            list(condition_fallback),
                            fallback_phrases=list(condition_fallback),
                        )
            return out
        if isinstance(node, list):
            return [_filter_condition_keywords(item) for item in node]
        return node

    filtered_conditions = _filter_condition_keywords(draft.rule.conditions)

    filtered_terms: list[RuleSuggestionDraftContextTerm] = []
    seen_term_keys: set[tuple[str, str, str]] = set()
    sanitized_term_values = _sanitize_context_term_values(
        [str(getattr(term, "term", "") or "") for term in list(draft.context_terms or [])],
        keyword_phrases=keyword_phrases,
    )
    allowed_term_folds = {_fold_text(value) for value in sanitized_term_values if _fold_text(value)}

    for term in list(draft.context_terms or []):
        term_text = str(getattr(term, "term", "") or "")
        if not _term_is_prompt_grounded(
            term_text,
            folded_prompt=folded_prompt,
            prompt_tokens=prompt_tokens,
            grounding_terms=grounding_terms,
        ):
            continue
        normalized_term = _normalize_phrase_text(term_text)
        cleaned_term = _sanitize_context_term_values(
            [normalized_term],
            keyword_phrases=keyword_phrases,
        )
        if not cleaned_term:
            continue
        normalized_term = cleaned_term[0]
        if _fold_text(normalized_term) not in allowed_term_folds:
            continue
        term_key = (
            str(getattr(term, "entity_type", "") or "").strip().upper(),
            _fold_text(normalized_term),
            _normalize_lang(str(getattr(term, "lang", "") or "vi")),
        )
        if (not term_key[0]) or (not term_key[1]) or term_key in seen_term_keys:
            continue
        seen_term_keys.add(term_key)
        filtered_terms.append(
            RuleSuggestionDraftContextTerm(
                entity_type=term_key[0],
                term=normalized_term,
                lang=term_key[2],
                weight=float(getattr(term, "weight", 1.0) or 1.0),
                window_1=int(getattr(term, "window_1", 60) or 60),
                window_2=int(getattr(term, "window_2", 20) or 20),
                enabled=bool(getattr(term, "enabled", True)),
            )
        )

    default_context_entity = "CUSTOM_SECRET"
    if filtered_terms:
        default_context_entity = filtered_terms[0].entity_type
    elif draft.context_terms:
        first_entity = str(getattr(draft.context_terms[0], "entity_type", "") or "").strip().upper()
        if first_entity:
            default_context_entity = first_entity

    sanitized_fallback_phrases = _sanitize_context_term_values(
        context_fallback_phrases,
        keyword_phrases=keyword_phrases,
    )
    for phrase in sanitized_fallback_phrases:
        folded_phrase = _fold_text(phrase)
        term_key = (default_context_entity, folded_phrase, "vi")
        if (not folded_phrase) or term_key in seen_term_keys:
            continue
        seen_term_keys.add(term_key)
        filtered_terms.append(
            RuleSuggestionDraftContextTerm(
                entity_type=default_context_entity,
                term=_normalize_phrase_text(phrase),
                lang="vi",
                weight=1.0,
                window_1=60,
                window_2=20,
                enabled=True,
            )
        )

    filtered_rule = draft.rule.model_copy(update={"conditions": filtered_conditions})
    return draft.model_copy(update={"rule": filtered_rule, "context_terms": filtered_terms})

def _select_primary_keyword_phrases(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
    prompt_keyword_bundle: PromptKeywordBundle,
    limit: int = 2,
) -> list[str]:
    def _is_clean_primary_keyword_candidate(value: str) -> bool:
        normalized = _normalize_phrase_text(value)
        folded = _fold_text(normalized)
        if not folded:
            return False
        tokens = [token for token in re.split(r"[^a-zA-Z0-9_]+", folded) if token]
        if not tokens:
            return False
        if len(tokens) > 4:
            return False
        if tokens[-1] in _PRIMARY_KEYWORD_TRAILING_NOISE_TOKENS:
            return False
        folded_prompt = _fold_text(prompt)
        prompt_tokens = [token for token in re.split(r"[^a-zA-Z0-9_]+", folded_prompt) if token]
        if len(prompt_tokens) > 5 and len(tokens) >= max(4, len(prompt_tokens) - 1) and folded in folded_prompt:
            return False
        return True

    safe_limit = max(1, min(int(limit), 4))
    target_phrases = _unique_phrase_values(_extract_target_phrases(prompt, limit=8))
    if target_phrases:
        return target_phrases[:safe_limit]

    bundle_phrases = _unique_phrase_values(list(prompt_keyword_bundle.get("phrases") or []))
    bundle_phrases = [
        value
        for value in bundle_phrases
        if (not _is_generic_modifier_phrase(value)) and _is_clean_primary_keyword_candidate(value)
    ]
    if bundle_phrases:
        return bundle_phrases[:safe_limit]

    existing_keywords = _sanitize_context_keyword_values(
        _collect_context_keyword_terms(draft.rule.conditions),
        fallback_phrases=[],
    )
    existing_keywords = _remove_redundant_subphrases(
        [
            value
            for value in existing_keywords
            if (not _is_generic_modifier_phrase(value)) and _is_clean_primary_keyword_candidate(value)
        ],
    )
    if existing_keywords:
        return existing_keywords[:safe_limit]

    business_phrases = _remove_redundant_subphrases(
        [value for value in _extract_business_noun_phrases(prompt, limit=6) if not _is_generic_modifier_phrase(value)]
    )
    if business_phrases:
        return business_phrases[:1]
    return []

def _select_supporting_context_phrases(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
    keyword_phrases: list[str],
) -> list[str]:
    folded_prompt = _fold_text(prompt)
    prompt_tokens = {
        token
        for token in re.split(r"[^a-zA-Z0-9_]+", folded_prompt)
        if token and token not in _PROMPT_GROUNDING_STOPWORDS
    }
    grounding_terms: set[str] = set()
    for phrase in _extract_target_phrases(prompt, limit=12):
        folded = _fold_text(phrase)
        if folded:
            grounding_terms.add(folded)
    for phrase in _extract_business_noun_phrases(prompt, limit=12):
        folded = _fold_text(phrase)
        if folded:
            grounding_terms.add(folded)
    for phrase in _extract_prompt_context_phrases(prompt, limit=12):
        folded = _fold_text(phrase)
        if folded:
            grounding_terms.add(folded)

    keyword_folds = {_fold_text(value) for value in keyword_phrases if _fold_text(value)}
    candidates: list[str] = []
    candidates.extend(str(getattr(term, "term", "") or "") for term in list(draft.context_terms or []))
    candidates.extend(_extract_business_noun_phrases(prompt, limit=10))
    candidates.extend(_extract_prompt_context_phrases(prompt, limit=10))

    out: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        simplified = _trim_context_phrase_against_keywords(raw, keyword_phrases)
        normalized = _normalize_phrase_text(simplified)
        folded = _fold_text(normalized)
        if not folded:
            continue
        if not _term_is_prompt_grounded(
            normalized,
            folded_prompt=folded_prompt,
            prompt_tokens=prompt_tokens,
            grounding_terms=grounding_terms,
        ):
            continue
        if folded in keyword_folds:
            continue
        if any((folded in keyword) and (folded != keyword) for keyword in keyword_folds):
            continue
        if any(
            re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", folded) is not None
            for keyword in keyword_folds
        ):
            continue
        if folded in seen:
            continue
        seen.add(folded)
        out.append(normalized)

    cleaned = _sanitize_context_term_values(out, keyword_phrases=keyword_phrases)
    cleaned = _remove_redundant_subphrases(
        cleaned,
        protected=set(_GENERIC_MODIFIER_PHRASES),
    )
    cleaned = [value for value in cleaned if _fold_text(value) not in keyword_folds]
    return cleaned[:6]

def _enforce_keyword_context_role_contract(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
    prompt_keyword_bundle: PromptKeywordBundle,
) -> tuple[RuleSuggestionDraftPayload, dict[str, Any]]:
    if _is_literal_secret_prompt(prompt) or _has_known_pii_intent(prompt):
        return draft, {"applied": False, "reason": "literal_or_known_pii_prompt"}

    keywords = _select_primary_keyword_phrases(
        prompt=prompt,
        draft=draft,
        prompt_keyword_bundle=prompt_keyword_bundle,
        limit=2,
    )
    if not keywords:
        fallback_context = _extract_prompt_context_phrases(prompt, limit=6)
        fallback_context = [value for value in fallback_context if not _is_generic_modifier_phrase(value)]
        if fallback_context:
            keywords = [fallback_context[0]]

    keywords = _unique_phrase_values(keywords)[:2]
    keywords = [value for value in keywords if not _is_generic_modifier_phrase(value)]

    if not keywords:
        fallback_candidates = _unique_phrase_values(
            _extract_target_phrases(prompt, limit=6)
            + _extract_business_noun_phrases(prompt, limit=6)
            + _extract_prompt_context_phrases(prompt, limit=6)
        )
        fallback_candidates = [
            value for value in fallback_candidates if not _is_generic_modifier_phrase(value)
        ]
        if fallback_candidates:
            keywords = fallback_candidates[:1]
        else:
            return draft, {"applied": False, "reason": "no_meaningful_keyword"}

    supporting_terms = _select_supporting_context_phrases(
        prompt=prompt,
        draft=draft,
        keyword_phrases=keywords,
    )
    keyword_folds = {_fold_text(value) for value in keywords if _fold_text(value)}
    supporting_terms = [
        value
        for value in supporting_terms
        if _fold_text(value) not in keyword_folds
    ]

    context_entity_type = "CUSTOM_SECRET"
    for term in list(draft.context_terms or []):
        entity_type = str(getattr(term, "entity_type", "") or "").strip().upper()
        if not entity_type or entity_type == "INTERNAL_CODE":
            continue
        context_entity_type = entity_type
        break
    if context_entity_type == "INTERNAL_CODE":
        context_entity_type = "CUSTOM_SECRET"

    normalized_terms = [
        RuleSuggestionDraftContextTerm(
            entity_type=context_entity_type,
            term=_normalize_phrase_text(value),
            lang="vi",
            weight=1.0,
            window_1=60,
            window_2=20,
            enabled=True,
        )
        for value in supporting_terms
        if _normalize_phrase_text(value)
    ]

    normalized_conditions: dict[str, Any] = {
        "all": [
            {
                "signal": {
                    "field": "context_keywords",
                    "any_of": keywords,
                }
            }
        ]
    }
    if not _is_simple_builder_compatible_conditions(normalized_conditions):
        normalized_conditions = {
            "all": [{"signal": {"field": "context_keywords", "any_of": keywords[:1]}}]
        }

    normalized_rule = draft.rule.model_copy(update={"conditions": normalized_conditions})
    finalized = draft.model_copy(update={"rule": normalized_rule, "context_terms": normalized_terms})
    return finalized, {
        "applied": True,
        "keywords": keywords,
        "support_terms": [str(term.term) for term in normalized_terms],
    }

def _contains_banned_debug_text(value: str) -> bool:
    folded = _fold_text(value)
    if not folded:
        return False
    return any(text in folded for text in _DRAFT_DEBUG_BANNED_TEXTS)

def _sanitize_debug_placeholder_text(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
) -> RuleSuggestionDraftPayload:
    rule = draft.rule
    name = str(rule.name or "").strip()
    description = str(rule.description or "").strip()

    if (not name) or _contains_banned_debug_text(name):
        name = "Suggested prompt policy"
    if _contains_banned_debug_text(description):
        description = f"Auto-generated suggestion from prompt: {prompt[:180]}"

    sanitized_terms: list[RuleSuggestionDraftContextTerm] = []
    for term in list(draft.context_terms or []):
        text = _normalize_phrase_text(str(term.term or ""))
        if (not text) or _contains_banned_debug_text(text):
            continue
        sanitized_terms.append(term.model_copy(update={"term": text}))

    sanitized_conditions = _sanitize_context_keyword_conditions(
        rule.conditions,
        fallback_phrases=[str(t.term or "") for t in sanitized_terms],
    )
    sanitized_rule = rule.model_copy(
        update={
            "name": name,
            "description": description or None,
            "conditions": sanitized_conditions,
        }
    )
    return draft.model_copy(update={"rule": sanitized_rule, "context_terms": sanitized_terms})

def _drop_internal_code_entity_fallback(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
) -> tuple[RuleSuggestionDraftPayload, dict[str, Any]]:
    sanitized_conditions, changed = _drop_entity_type_from_conditions(
        draft.rule.conditions,
        blocked_entity_types={"INTERNAL_CODE"},
    )
    if not changed:
        return draft, {"applied": False, "fallback_rebuilt": False}

    fallback_rebuilt = False
    if sanitized_conditions is None:
        h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        keyword_bundle = _prompt_keywords(prompt, limit=8)
        phrases = list(keyword_bundle.get("phrases") or [])
        if not phrases:
            phrases = _extract_prompt_context_phrases(prompt, limit=6)
        fallback = _build_generic_prompt_keyword_draft(
            prompt=prompt,
            action=draft.rule.action,
            stable_suffix=h,
            phrases=phrases or ["context"],
        )
        sanitized_conditions = fallback.rule.conditions
        fallback_rebuilt = True

    sanitized_rule = draft.rule.model_copy(update={"conditions": sanitized_conditions})
    sanitized_draft = draft.model_copy(update={"rule": sanitized_rule})
    return sanitized_draft, {"applied": True, "fallback_rebuilt": fallback_rebuilt}

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
    return collect_runtime_context_keyword_terms(conditions)

def _has_context_keyword_signal(conditions: Any) -> bool:
    return has_runtime_context_keyword_signal(conditions)

def _is_code_like_term(value: str) -> bool:
    return runtime_is_code_like_term(value)

def _prompt_code_like_terms(prompt: str) -> set[str]:
    return runtime_prompt_code_like_terms(prompt)

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
    allow_unprompted_code_terms = prompt is None or _is_custom_secret_prompt(prompt or "")
    meta = evaluate_draft_runtime_usability(
        draft=draft,
        prompt=prompt,
        allow_unprompted_code_terms=allow_unprompted_code_terms,
    )
    meta["warnings"] = _to_str_list(meta.get("warnings"))
    meta["abstract_terms"] = _to_str_list(meta.get("abstract_terms"))
    return meta

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

    if warnings and _is_literal_secret_prompt(prompt):
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
    literal_detection = _literal_detection(prompt, limit=8)

    if (
        literal_detection.intent_literal
        and (not literal_detection.known_pii_type)
        and (not literal_detection.candidate_tokens)
    ):
        guarded = _build_literal_refinement_draft(
            prompt=prompt,
            action=guarded.rule.action,
            stable_suffix=h,
        )
        mismatch_detected = True
        applied = True
        reasons.append("literal_not_supported_requires_refine")

    if _is_literal_secret_prompt(prompt):
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

    internal_code_guarded, internal_code_guard_meta = _drop_internal_code_entity_fallback(
        prompt=prompt,
        draft=guarded,
    )
    if bool(internal_code_guard_meta.get("applied")):
        guarded = internal_code_guarded
        mismatch_detected = True
        applied = True
        reasons.append("removed_internal_code_entity_fallback")

    explicit_action_intent = _explicit_action_intent_from_prompt(prompt)
    if explicit_action_intent and guarded.rule.action != explicit_action_intent:
        guarded = _realign_action_dependent_fields_after_override(
            prompt=prompt,
            draft=guarded,
            final_action=explicit_action_intent,
        )
        mismatch_detected = True
        applied = True
        reasons.append(f"action_intent_auto_repair_{explicit_action_intent.value}")

    return guarded, {
        "applied": bool(applied),
        "mismatch_detected": bool(mismatch_detected),
        "reasons": reasons,
    }

def _known_pii_fallback_profile(
    *,
    entity_type: str,
    action: RuleAction,
) -> tuple[str, RuleSeverity, int, float]:
    et = str(entity_type or "").strip().upper()

    if et == "EMAIL":
        if action == RuleAction.block:
            return "Chặn email", RuleSeverity.high, 90, 0.80
        return "Che email", RuleSeverity.low, 30, 0.80

    if et == "PHONE":
        if action == RuleAction.block:
            return "Chặn số điện thoại", RuleSeverity.high, 100, 0.80
        return "Che SĐT", RuleSeverity.medium, 60, 0.80

    if et == "TAX_ID":
        if action == RuleAction.block:
            return "Chặn mã số thuế", RuleSeverity.high, 95, 0.80
        return "Che mã số thuế", RuleSeverity.medium, 55, 0.80

    if et == "CCCD":
        if action == RuleAction.block:
            return "Chặn CCCD", RuleSeverity.high, 100, 0.85
        return "Che CCCD", RuleSeverity.medium, 80, 0.85

    if action == RuleAction.block:
        return f"Chặn {et or 'PII'}", RuleSeverity.high, 90, 0.80
    return f"Che {et or 'PII'}", RuleSeverity.medium, 70, 0.80

def _known_pii_label(entity_type: str) -> str:
    et = str(entity_type or "").strip().upper()
    if et == "EMAIL":
        return "email"
    if et == "PHONE":
        return "số điện thoại"
    if et == "TAX_ID":
        return "mã số thuế"
    if et == "CCCD":
        return "CCCD"
    return et or "PII"

def _infer_known_pii_entity_from_draft(
    draft: RuleSuggestionDraftPayload,
) -> str | None:
    known = {"EMAIL", "PHONE", "TAX_ID", "CCCD"}
    for entity_type in _extract_entity_types(draft.rule.conditions):
        et = str(entity_type or "").strip().upper()
        if et in known:
            return et

    stable_key = str(draft.rule.stable_key or "").strip().lower()
    if ".email." in stable_key or stable_key.endswith(".email"):
        return "EMAIL"
    if ".phone." in stable_key or stable_key.endswith(".phone"):
        return "PHONE"
    if ".tax_id." in stable_key or ".tax." in stable_key or stable_key.endswith(".tax"):
        return "TAX_ID"
    if ".cccd." in stable_key or stable_key.endswith(".cccd"):
        return "CCCD"
    return None

def _infer_known_pii_entity_from_prompt(prompt: str) -> str | None:
    detected = _literal_detection(prompt)
    if detected.known_pii_type:
        return str(detected.known_pii_type).strip().upper()

    p = str(prompt or "")
    if _has_any(p, ["cccd", "cmnd", "can cuoc", "căn cước"]):
        return "CCCD"
    if _has_any(p, ["tax", "mst", "ma so thue", "mã số thuế"]):
        return "TAX_ID"
    if _has_any(p, ["phone", "sdt", "so dien thoai", "số điện thoại", "hotline"]):
        return "PHONE"
    if _has_any(p, ["email", "mail", "e-mail", "gmail"]):
        return "EMAIL"
    return None

def _canonicalize_known_pii_rule_for_duplicate_check(
    *,
    prompt: str,
    rule: RuleSuggestionDraftRule,
) -> RuleSuggestionDraftRule:
    if rule.action not in {RuleAction.mask, RuleAction.block}:
        return rule

    inferred_from_draft = _infer_known_pii_entity_from_draft(
        RuleSuggestionDraftPayload(rule=rule, context_terms=[])
    )
    entity_type = inferred_from_draft or _infer_known_pii_entity_from_prompt(prompt)
    if not entity_type:
        return rule

    rule_name, severity, priority, min_score = _known_pii_fallback_profile(
        entity_type=entity_type,
        action=rule.action,
    )
    condition_leaf: dict[str, Any] = {"entity_type": entity_type}
    if min_score > 0:
        condition_leaf["min_score"] = float(min_score)

    return rule.model_copy(
        update={
            "name": rule_name,
            "scope": RuleScope.prompt,
            "conditions": {"any": [condition_leaf]},
            "severity": severity,
            "priority": priority,
            "rag_mode": RagMode.off,
            "enabled": True,
        }
    )

def _canonicalize_known_pii_context_terms(
    *,
    entity_type: str,
    context_terms: list[RuleSuggestionDraftContextTerm],
) -> list[RuleSuggestionDraftContextTerm]:
    et = str(entity_type or "").strip().upper()
    if et not in _KNOWN_PII_RUNTIME_ENTITIES:
        return list(context_terms or [])

    allowlist = {
        _fold_text(value)
        for value in _KNOWN_PII_CONTEXT_TERM_ALLOWLIST.get(et, set())
        if _fold_text(value)
    }
    out: list[RuleSuggestionDraftContextTerm] = []
    seen: set[tuple[str, str, str]] = set()

    for term in list(context_terms or []):
        term_entity = str(getattr(term, "entity_type", "") or "").strip().upper()
        if term_entity != et:
            continue
        text = _fold_text(str(getattr(term, "term", "") or ""))
        if len(text) < 3:
            continue
        if allowlist and text not in allowlist:
            continue
        lang = _normalize_lang(str(getattr(term, "lang", "") or "vi"))
        key = (et, text, lang)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            RuleSuggestionDraftContextTerm(
                entity_type=et,
                term=text,
                lang=lang,
                weight=float(getattr(term, "weight", 1.0) or 1.0),
                window_1=int(getattr(term, "window_1", 60) or 60),
                window_2=int(getattr(term, "window_2", 20) or 20),
                enabled=bool(getattr(term, "enabled", True)),
            )
        )
        if len(out) >= 4:
            break

    if out:
        return out

    default_term = _KNOWN_PII_DEFAULT_CONTEXT_TERM.get(et)
    if not default_term:
        return []
    return [
        RuleSuggestionDraftContextTerm(
            entity_type=et,
            term=default_term,
            lang="vi",
            weight=1.0,
            window_1=60,
            window_2=20,
            enabled=True,
        )
    ]

def _canonicalize_known_pii_draft_for_runtime(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
) -> tuple[RuleSuggestionDraftPayload, dict[str, Any]]:
    if draft.rule.action not in {RuleAction.mask, RuleAction.block}:
        return draft, {"applied": False, "entity_type": None}

    inferred_from_draft = _infer_known_pii_entity_from_draft(draft)
    inferred_from_prompt = _infer_known_pii_entity_from_prompt(prompt)
    entity_type = inferred_from_draft or inferred_from_prompt
    if entity_type not in _KNOWN_PII_RUNTIME_ENTITIES:
        return draft, {"applied": False, "entity_type": None}

    # Only prompt-derived canonicalization for known-PII focused asks.
    # Avoid collapsing mixed semantic prompts (e.g. payroll + external email) into pure PII rules.
    if (not inferred_from_draft) and inferred_from_prompt:
        if _extract_persona_hint(draft.rule.conditions):
            return draft, {"applied": False, "entity_type": None}
        keyword_terms = {
            _fold_text(value)
            for value in _collect_context_keyword_terms(draft.rule.conditions)
            if _fold_text(value)
        }
        allowlist = {
            _fold_text(value)
            for value in _KNOWN_PII_CONTEXT_TERM_ALLOWLIST.get(entity_type, set())
            if _fold_text(value)
        }
        if keyword_terms and any(term not in allowlist for term in keyword_terms):
            return draft, {"applied": False, "entity_type": None}

    canonical_rule = _canonicalize_known_pii_rule_for_duplicate_check(
        prompt=prompt,
        rule=draft.rule,
    )
    canonical_terms = _canonicalize_known_pii_context_terms(
        entity_type=entity_type,
        context_terms=list(draft.context_terms or []),
    )
    canonical_draft = draft.model_copy(
        update={
            "rule": canonical_rule,
            "context_terms": canonical_terms,
        }
    )
    applied = canonical_draft.model_dump() != draft.model_dump()
    return canonical_draft, {"applied": applied, "entity_type": entity_type}

def _rewrite_stable_key_action_suffix(stable_key: str, action: RuleAction) -> str:
    key = str(stable_key or "").strip().lower()
    if not key:
        return key
    if key.endswith(".block") or key.endswith(".mask") or key.endswith(".warn"):
        base = key.rsplit(".", 1)[0]
        return f"{base}.{action.value}"
    return key

def _realign_action_dependent_fields_after_override(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
    final_action: RuleAction,
) -> RuleSuggestionDraftPayload:
    updated_rule = draft.rule.model_copy(update={"action": final_action})

    entity_type = _infer_known_pii_entity_from_draft(draft)
    if entity_type:
        rule_name, severity, priority, _ = _known_pii_fallback_profile(
            entity_type=entity_type,
            action=final_action,
        )
        stable_key = _rewrite_stable_key_action_suffix(
            str(updated_rule.stable_key or ""),
            final_action,
        )
        if not stable_key:
            stable_key = f"personal.custom.pii.{entity_type.lower()}.{final_action.value}"
        elif f".{final_action.value}" not in stable_key:
            stable_key = f"personal.custom.pii.{entity_type.lower()}.{final_action.value}"

        verb = "Chặn" if final_action == RuleAction.block else "Che"
        label = _known_pii_label(entity_type)
        updated_rule = updated_rule.model_copy(
            update={
                "stable_key": stable_key,
                "name": rule_name,
                "description": f"{verb} thông tin {label} theo yêu cầu từ prompt: {prompt[:180]}",
                "severity": severity,
                "priority": priority,
            }
        )
        return draft.model_copy(update={"rule": updated_rule})

    stable_key = _rewrite_stable_key_action_suffix(
        str(updated_rule.stable_key or ""),
        final_action,
    )
    if stable_key:
        updated_rule = updated_rule.model_copy(update={"stable_key": stable_key})
    return draft.model_copy(update={"rule": updated_rule})

def _align_draft_with_prompt(
    prompt: str, draft: RuleSuggestionDraftPayload
) -> RuleSuggestionDraftPayload:
    p = prompt.lower()
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    code_tokens = _extract_code_like_tokens(prompt, limit=4)

    if _is_literal_secret_prompt(prompt) and code_tokens:
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

    if _is_literal_secret_prompt(prompt) and code_tokens:
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

_LITERAL_GENERIC_TERMS = {
    "phone",
    "phone number",
    "email",
    "cccd",
    "tax id",
    "tax code",
    "mst",
    "ma so thue",
    "hotline",
    "sdt",
    "so dien thoai",
    "mask",
    "block",
    "allow",
    "secret",
    "token",
    "internal",
    "internal code",
    "custom secret",
}

_FINGERPRINT_SECRET_ENTITY_TYPES = {
    "INTERNAL_CODE",
    "CUSTOM_SECRET",
    "PROPRIETARY_IDENTIFIER",
    "API_SECRET",
}

_FINGERPRINT_PII_ENTITY_TYPES = {
    "PHONE",
    "EMAIL",
    "CCCD",
    "TAX_ID",
    "CREDIT_CARD",
}

_KNOWN_PII_RUNTIME_ENTITIES = {"PHONE", "EMAIL", "CCCD", "TAX_ID"}

_KNOWN_PII_CONTEXT_TERM_ALLOWLIST = {
    "PHONE": {"phone", "sdt", "so dien thoai", "dien thoai", "hotline"},
    "EMAIL": {"email", "mail", "e-mail", "gmail", "email ca nhan", "personal email"},
    "CCCD": {"cccd", "cmnd", "can cuoc", "can cuoc cong dan"},
    "TAX_ID": {"mst", "ma so thue", "tax id", "tax code", "tin", "taxpayer id"},
}

_KNOWN_PII_DEFAULT_CONTEXT_TERM = {
    "PHONE": "so dien thoai",
    "EMAIL": "email",
    "CCCD": "cccd",
    "TAX_ID": "ma so thue",
}

def _slug_segment(value: str) -> str:
    text = _fold_text(value)
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text

def _normalized_context_term_rows(
    draft: RuleSuggestionDraftPayload,
) -> list[tuple[str, str, str]]:
    rows: set[tuple[str, str, str]] = set()
    for row in list(draft.context_terms or []):
        entity_type = str(getattr(row, "entity_type", "") or "").strip().upper()
        term = _fold_text(str(getattr(row, "term", "") or ""))
        lang = _fold_text(str(getattr(row, "lang", "") or "vi")) or "vi"
        if not entity_type or not term:
            continue
        rows.add((entity_type, term, lang))
    return sorted(rows, key=lambda x: (x[0], x[1], x[2]))

def _looks_literal_specific_term(term: str) -> bool:
    text = _fold_text(term)
    if not text:
        return False
    if text in _LITERAL_GENERIC_TERMS or text in ABSTRACT_CONTEXT_KEYWORDS:
        return False
    return score_identifier_token(text) >= 0.45

def is_literal_specific(draft: RuleSuggestionDraftPayload) -> bool:
    rows = _normalized_context_term_rows(draft)
    if not rows:
        return False
    if len(rows) > 5:
        return False

    specific_terms = [term for _et, term, _lang in rows if _looks_literal_specific_term(term)]
    if not specific_terms:
        return False
    return True

def _literal_terms_fingerprint(draft: RuleSuggestionDraftPayload) -> str:
    rows = _normalized_context_term_rows(draft)
    if not rows:
        return ""
    body = [{"entity_type": et, "term": term, "lang": lang} for et, term, lang in rows]
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]

def _literal_condition_terms_from_context(
    draft: RuleSuggestionDraftPayload,
) -> list[str]:
    enabled_terms: list[str] = []
    fallback_terms: list[str] = []
    seen_enabled: set[str] = set()
    seen_fallback: set[str] = set()

    for term in list(draft.context_terms or []):
        value = _fold_text(str(getattr(term, "term", "") or ""))
        if not value or not _looks_literal_specific_term(value):
            continue
        if bool(getattr(term, "enabled", True)):
            if value in seen_enabled:
                continue
            seen_enabled.add(value)
            enabled_terms.append(value)
            continue
        if value in seen_fallback:
            continue
        seen_fallback.add(value)
        fallback_terms.append(value)

    return enabled_terms or fallback_terms

def _replace_context_keyword_literals(
    node: Any,
    *,
    terms: list[str],
) -> Any:
    if not terms:
        return node

    if isinstance(node, dict):
        out = {k: _replace_context_keyword_literals(v, terms=terms) for k, v in node.items()}
        signal = out.get("signal")
        if not isinstance(signal, dict):
            return out

        field_name = _fold_text(str(signal.get("field") or ""))
        if field_name != "context_keywords":
            return out

        signal_out = dict(signal)
        list_terms = list(terms)
        scalar_term = list_terms[0]
        replaced = False

        for op in ("any_of", "in"):
            if op not in signal_out:
                continue
            signal_out[op] = list_terms
            replaced = True

        for op in ("equals", "contains", "startswith", "regex"):
            if op not in signal_out:
                continue
            signal_out[op] = scalar_term
            replaced = True

        if replaced:
            out["signal"] = signal_out
        return out

    if isinstance(node, list):
        return [_replace_context_keyword_literals(item, terms=terms) for item in node]

    return node

def _realign_literal_specific_draft(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
) -> RuleSuggestionDraftPayload:
    aligned = draft
    literal_terms = _literal_condition_terms_from_context(aligned)
    if literal_terms and _has_context_keyword_signal(aligned.rule.conditions):
        synced_conditions = _replace_context_keyword_literals(
            aligned.rule.conditions,
            terms=literal_terms,
        )
        aligned = aligned.model_copy(
            update={
                "rule": aligned.rule.model_copy(update={"conditions": synced_conditions}),
            }
        )

    return _ensure_company_stable_key(prompt=prompt, draft=aligned)

def _fingerprint_category_and_entity(draft: RuleSuggestionDraftPayload) -> tuple[str, str]:
    rows = _normalized_context_term_rows(draft)
    entity_type = rows[0][0] if rows else "LITERAL"
    if entity_type in _FINGERPRINT_SECRET_ENTITY_TYPES:
        category = "secret"
    elif entity_type in _FINGERPRINT_PII_ENTITY_TYPES:
        category = "pii"
    elif entity_type.startswith("PERSONA_"):
        category = "context"
    else:
        category = "literal"

    entity_segment = entity_type.lower()
    if entity_type.startswith("PERSONA_"):
        entity_segment = entity_type.removeprefix("PERSONA_").lower()
    return _slug_segment(category) or "literal", _slug_segment(entity_segment) or "literal"

def _build_literal_specific_stable_key(draft: RuleSuggestionDraftPayload) -> str:
    fingerprint = _literal_terms_fingerprint(draft)
    if not fingerprint:
        return ""
    category, entity = _fingerprint_category_and_entity(draft)
    action = _slug_segment(str(draft.rule.action.value))
    key = f"personal.{category}.{entity}.{action or 'mask'}.{fingerprint}"
    return key[:200].strip(".")

def _ensure_company_stable_key(
    *,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
) -> RuleSuggestionDraftPayload:
    if is_literal_specific(draft):
        literal_key = _build_literal_specific_stable_key(draft)
        if literal_key:
            rule = draft.rule.model_copy(update={"stable_key": literal_key})
            return draft.model_copy(update={"rule": rule})

    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:10]
    stable_key = str(draft.rule.stable_key or "").strip().lower()
    stable_key = re.sub(r"[^a-z0-9._-]+", ".", stable_key)
    stable_key = re.sub(r"\.+", ".", stable_key).strip(".")

    if not stable_key or stable_key.startswith("global."):
        slug = ".".join(sorted(_tokenize_for_score(prompt)))[:60].strip(".")
        if not slug:
            slug = f"suggested.{h}"
        stable_key = f"personal.custom.{slug}.{h}"
    elif not stable_key.startswith("personal."):
        stable_key = f"personal.custom.{stable_key}"

    stable_key = stable_key[:200].strip(".")
    if not stable_key:
        stable_key = f"personal.custom.suggested.{h}"

    rule = draft.rule.model_copy(update={"stable_key": stable_key})
    return draft.model_copy(update={"rule": rule})
