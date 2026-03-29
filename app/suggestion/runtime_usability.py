from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.suggestion.literal_detector import analyze_literal_prompt, score_identifier_token
from app.suggestion.schemas import RuleSuggestionDraftPayload


ABSTRACT_CONTEXT_KEYWORDS = {
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

_EXACT_ANCHOR_ENTITY_TYPES = {"INTERNAL_CODE", "CUSTOM_SECRET", "PROPRIETARY_IDENTIFIER"}
_PERSONA_PREFIX = "PERSONA_"


def fold_text(value: str) -> str:
    raw = str(value or "").lower().replace("\u0111", "d")
    normalized = unicodedata.normalize("NFKD", raw)
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", no_marks).strip()


def collect_context_keyword_terms(conditions: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def _push(value: Any) -> None:
        text = fold_text(str(value or ""))
        if not text or text in seen:
            return
        seen.add(text)
        out.append(text)

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            signal = node.get("signal")
            if isinstance(signal, dict):
                field_name = fold_text(str(signal.get("field") or ""))
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


def has_context_keyword_signal(conditions: Any) -> bool:
    if isinstance(conditions, dict):
        signal = conditions.get("signal")
        if isinstance(signal, dict):
            field_name = fold_text(str(signal.get("field") or ""))
            if field_name == "context_keywords":
                return True
        return any(has_context_keyword_signal(v) for v in conditions.values())
    if isinstance(conditions, list):
        return any(has_context_keyword_signal(x) for x in conditions)
    return False


def is_code_like_term(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return score_identifier_token(text) >= 0.32


def prompt_code_like_terms(prompt: str) -> set[str]:
    out: set[str] = set()
    detection = analyze_literal_prompt(prompt, limit=12)
    for token in detection.candidate_tokens:
        text = fold_text(token)
        if text:
            out.add(text)
    return out


def _anchor_terms_from_draft(
    draft: RuleSuggestionDraftPayload,
) -> tuple[set[str], set[str]]:
    exact_anchor_terms: set[str] = set()
    persona_anchor_terms: set[str] = set()

    for term in list(draft.context_terms or []):
        if not bool(getattr(term, "enabled", True)):
            continue
        entity_type = str(getattr(term, "entity_type", "") or "").strip().upper()
        text = fold_text(str(getattr(term, "term", "") or ""))
        if not entity_type or not text:
            continue
        if entity_type in _EXACT_ANCHOR_ENTITY_TYPES:
            exact_anchor_terms.add(text)
        if entity_type.startswith(_PERSONA_PREFIX):
            persona_anchor_terms.add(text)

    return exact_anchor_terms, persona_anchor_terms


def evaluate_runtime_usability(
    *,
    draft: RuleSuggestionDraftPayload,
    prompt: str | None = None,
    allow_unprompted_code_terms: bool = False,
) -> dict[str, Any]:
    warnings: list[str] = []
    keyword_terms = collect_context_keyword_terms(draft.rule.conditions)
    has_keyword_signal = has_context_keyword_signal(draft.rule.conditions)
    if has_keyword_signal and not keyword_terms:
        warnings.append("context_keywords_signal_without_runtime_terms")

    detection = analyze_literal_prompt(prompt or "", limit=8) if prompt is not None else None
    if (
        detection is not None
        and detection.intent_literal
        and not detection.known_pii_type
        and not detection.candidate_tokens
    ):
        warnings.append("literal_token_not_supported_yet")

    if not keyword_terms:
        warnings = list(dict.fromkeys(warnings))
        return {
            "runtime_usable": not warnings,
            "warnings": warnings,
            "abstract_terms": [],
            "anchored_code_terms": [],
            "missing_code_terms": [],
        }

    abstract_terms = [
        term for term in keyword_terms if term in ABSTRACT_CONTEXT_KEYWORDS
    ]
    concrete_terms = [
        term for term in keyword_terms if term not in ABSTRACT_CONTEXT_KEYWORDS
    ]
    code_keyword_terms = {term for term in keyword_terms if is_code_like_term(term)}
    prompt_code_terms = prompt_code_like_terms(prompt or "")
    exact_anchor_terms, persona_anchor_terms = _anchor_terms_from_draft(draft)

    missing_code_terms = sorted(code_keyword_terms - exact_anchor_terms)
    anchored_code_terms = sorted(code_keyword_terms & exact_anchor_terms)
    has_code_anchor = bool(anchored_code_terms)

    if code_keyword_terms and not has_code_anchor:
        warnings.append("code_like_context_keywords_without_exact_anchor")

    if (not allow_unprompted_code_terms) and code_keyword_terms:
        unexpected = sorted(code_keyword_terms - prompt_code_terms)
        if unexpected:
            warnings.append("unexpected_code_like_term_not_in_prompt")

    if (
        detection is not None
        and detection.intent_literal
        and not code_keyword_terms
        and concrete_terms
    ):
        unresolved_terms = [
            term
            for term in concrete_terms
            if term not in persona_anchor_terms and term not in exact_anchor_terms
        ]
        if unresolved_terms:
            warnings.append("literal_context_keywords_without_runtime_anchor")

    persona_anchor_hits = [
        term for term in concrete_terms if term in persona_anchor_terms
    ]
    has_persona_anchor = bool(persona_anchor_hits)
    has_runtime_anchor = has_code_anchor or has_persona_anchor

    if abstract_terms and (not concrete_terms) and (not has_runtime_anchor):
        warnings.append("abstract_context_keywords_not_runtime_usable")

    if ("exact" in abstract_terms) and (not has_runtime_anchor):
        warnings.append("context_keyword_exact_without_runtime_anchor")

    if ("token" in abstract_terms) and (not has_runtime_anchor):
        warnings.append("context_keyword_token_without_runtime_anchor")

    warnings = list(dict.fromkeys(warnings))
    return {
        "runtime_usable": not warnings,
        "warnings": warnings,
        "abstract_terms": list(dict.fromkeys(abstract_terms)),
        "anchored_code_terms": anchored_code_terms,
        "missing_code_terms": missing_code_terms,
    }
