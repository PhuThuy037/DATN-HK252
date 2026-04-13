from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import TypedDict

from app.suggestion.suggestion_spacy_extractor import extract_with_spacy


logger = logging.getLogger(__name__)

USE_SPACY_EXTRACTOR = os.getenv("USE_SPACY_EXTRACTOR", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


class PromptKeywordBundle(TypedDict):
    phrases: list[str]
    tokens: list[str]


@dataclass(frozen=True)
class HybridExtractionResult:
    target_entities: list[str]
    business_phrases: list[str]
    context_modifiers: list[str]
    helper_tokens: list[str]


_INSIGHT_STOP_WORDS = {
    "va",
    "voi",
    "cho",
    "che",
    "an",
    "mask",
    "block",
    "allow",
    "chan",
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
    "ma",
    "m",
}

# Audit note:
# - The spaCy sidecar now covers most label-style prefixes below via matcher/ruler.
# - Keep this regex as the primary high-precision fallback for now.
# - Deprecated candidates once spaCy coverage is proven stable:
#   can bo, quan ly, cong ty, tap doan, bo phan, phong ban, du an,
#   tro giang, co van, giang vien, to chuc, ong, ba
_TARGET_ENTITY_LABEL_PATTERN = re.compile(
    r"(?iu)\b(?:"
    r"cán\s+bộ|can\s+bo|"
    r"quản\s+lý|quan\s+ly|"
    r"trưởng\s+nhóm|truong\s+nhom|"
    r"giám\s+đốc|giam\s+doc|"
    r"nhân\s+viên|nhan\s+vien|"
    r"công\s+ty|cong\s+ty|"
    r"tập\s+đoàn|tap\s+doan|"
    r"bộ\s+phận|bo\s+phan|"
    r"phòng|phong|"
    r"trung\s+tâm|trung\s+tam|"
    r"phòng\s+ban|phong\s+ban|"
    r"dự\s+án|du\s+an|"
    r"trợ\s+giảng|tro\s+giang|"
    r"cố\s+vấn|co\s+van|"
    r"giảng\s+viên|giang\s+vien|"
    r"tổ\s+chức|to\s+chuc|"
    r"ông|ong|bà|ba"
    r")\s+(?:[0-9A-Za-zÀ-ỹĐđ._-]+(?:\s+[0-9A-Za-zÀ-ỹĐđ._-]+){0,4})"
)
_TARGET_ENTITY_NAMED_PERSON_PATTERN = re.compile(
    r"(?iu)\b(?:người|nguoi)(?:\s+[0-9A-Za-zÀ-ỹĐđ._-]+){0,5}\s+(?:tên|ten)\s+[0-9A-Za-zÀ-ỹĐđ._-]+"
)
_TARGET_ENTITY_FAMILY_BY_PREFIX = {
    "can bo": "person_target",
    "quan ly": "person_target",
    "truong nhom": "person_target",
    "giam doc": "person_target",
    "nhan vien": "person_target",
    "ong": "person_target",
    "ba": "person_target",
    "tro giang": "person_target",
    "co van": "person_target",
    "giang vien": "person_target",
    "nguoi": "person_target",
    "cong ty": "company_target",
    "tap doan": "company_target",
    "truong": "school_target",
    "bo phan": "org_target",
    "phong": "org_target",
    "trung tam": "org_target",
    "phong ban": "org_target",
    "to chuc": "org_target",
    "du an": "project_target",
}
_TARGET_ENTITY_RELATION_PREFIX_PATTERN = "|".join(
    re.escape(prefix).replace(r"\ ", r"\s+")
    for prefix in sorted(_TARGET_ENTITY_FAMILY_BY_PREFIX.keys(), key=len, reverse=True)
)
_TARGET_ENTITY_RELATION_ANCHORED_PATTERN = re.compile(
    rf"(?iu)(?<![a-z0-9])(?:ve|cua|lien\s+quan\s+den|hoi\s+ve)\s+"
    rf"((?:{_TARGET_ENTITY_RELATION_PREFIX_PATTERN})\s+[a-z0-9_.-]+(?:\s+[a-z0-9_.-]+){{0,4}})(?![a-z0-9])"
)
_RETRIEVAL_STOP_WORDS = set(_INSIGHT_STOP_WORDS) | {
    "toi",
    "muon",
    "thong",
    "tin",
    "ve",
    "noi",
    "ve",
    "thongtin",
}

# Audit note:
# - spaCy phrase matcher already covers all exact phrases below.
# - These exact phrase patterns are now deprecated candidates, but remain active
#   as deterministic fallback and for rule-only mode.
_PROMPT_CONTEXT_PHRASE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?<![a-z0-9])tai lieu noi bo(?![a-z0-9])", "tai lieu noi bo"),
    (r"(?<![a-z0-9])chua cong bo(?![a-z0-9])", "chua cong bo"),
    (r"(?<![a-z0-9])noi xau(?![a-z0-9])", "noi xau"),
    (r"(?<![a-z0-9])boi nho(?![a-z0-9])", "boi nho"),
    (r"(?<![a-z0-9])noi bo(?![a-z0-9])", "noi bo"),
    (r"(?<![a-z0-9])ho so ky luat(?![a-z0-9])", "ho so ky luat"),
    (r"(?<![a-z0-9])ke hoach sa thai(?![a-z0-9])", "ke hoach sa thai"),
    (r"(?<![a-z0-9])bao cao tai chinh(?![a-z0-9])", "bao cao tai chinh"),
    (r"(?<![a-z0-9])bien ban hop chien luoc(?![a-z0-9])", "bien ban hop chien luoc"),
    (r"(?<![a-z0-9])danh sach thuong quy(?![a-z0-9])", "danh sach thuong quy"),
    (r"(?<![a-z0-9])ngan sach van hanh(?![a-z0-9])", "ngan sach van hanh"),
    (r"(?<![a-z0-9])thong tin mat(?![a-z0-9])", "thong tin mat"),
    (r"(?<![a-z0-9])quy trinh xu ly su co(?![a-z0-9])", "quy trinh xu ly su co"),
    (r"(?<![a-z0-9])ke hoach mo rong thi truong(?![a-z0-9])", "ke hoach mo rong thi truong"),
    (r"(?<![a-z0-9])bao cao loi nhuan quy(?![a-z0-9])", "bao cao loi nhuan quy"),
)

# Audit note:
# - Keep these regex families for now. spaCy currently covers only fixed business
#   phrases, while these patterns still help with open-ended noun phrases such as
#   "ke hoach ...", "bao cao ...", "quy trinh ...", "thong tin ...".
# - These are not deprecated yet.
_BUSINESS_NOUN_PHRASE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<![a-z0-9])(ho so(?:\s+[a-z0-9_.-]+){1,2})(?![a-z0-9])"),
    re.compile(r"(?<![a-z0-9])(ke hoach(?:\s+[a-z0-9_.-]+){2,4})(?![a-z0-9])"),
    re.compile(r"(?<![a-z0-9])(bao cao(?:\s+[a-z0-9_.-]+){2,3})(?![a-z0-9])"),
    re.compile(r"(?<![a-z0-9])(bien ban(?:\s+[a-z0-9_.-]+){1,4})(?![a-z0-9])"),
    re.compile(r"(?<![a-z0-9])(danh sach(?:\s+[a-z0-9_.-]+){2,3})(?![a-z0-9])"),
    re.compile(r"(?<![a-z0-9])(ngan sach(?:\s+[a-z0-9_.-]+){2,3})(?![a-z0-9])"),
    re.compile(r"(?<![a-z0-9])(tai lieu(?:\s+[a-z0-9_.-]+){1,2})(?![a-z0-9])"),
    re.compile(r"(?<![a-z0-9])(quy trinh(?:\s+[a-z0-9_.-]+){2,4})(?![a-z0-9])"),
    re.compile(r"(?<![a-z0-9])(thong tin(?:\s+[a-z0-9_.-]+){1,2})(?![a-z0-9])"),
)
_BUSINESS_CONTEXT_QUALIFIER_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?<![a-z0-9])noi bo(?![a-z0-9])"), "noi bo"),
    (re.compile(r"(?<![a-z0-9])chua cong bo(?![a-z0-9])"), "chua cong bo"),
    (re.compile(r"(?<![a-z0-9])boi nho(?![a-z0-9])"), "boi nho"),
)
_GENERIC_MODIFIER_PHRASES = {"noi bo", "chua cong bo"}
_PROMPT_GROUNDING_STOPWORDS = set(_RETRIEVAL_STOP_WORDS) | {
    "cac",
    "nhung",
    "noi",
    "dung",
    "ve",
}


def _fold_text(value: str) -> str:
    raw = str(value or "").lower().replace("\u0111", "d")
    normalized = unicodedata.normalize("NFKD", raw)
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", no_marks).strip()


def _normalize_phrase_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return text.strip(" \t\r\n,.;:!?\"'()[]{}")


def _target_family_for_phrase(phrase: str) -> str | None:
    folded = _fold_text(phrase)
    if not folded:
        return None
    for prefix, family in _TARGET_ENTITY_FAMILY_BY_PREFIX.items():
        pattern = rf"^{re.escape(prefix)}(?:\s+|$)"
        if re.search(pattern, folded):
            return family
    return None


def _extract_target_phrases(prompt: str, *, limit: int = 4) -> list[str]:
    raw = str(prompt or "")
    safe_limit = max(1, min(int(limit), 32))
    out: list[str] = []
    seen: set[str] = set()

    def _append(value: str) -> bool:
        phrase = _normalize_phrase_text(value)
        if not phrase:
            return False
        folded = _fold_text(phrase)
        if not folded or folded in seen:
            return False
        seen.add(folded)
        out.append(phrase)
        return len(out) >= safe_limit

    folded_prompt = _fold_text(raw)
    for match in _TARGET_ENTITY_RELATION_ANCHORED_PATTERN.finditer(folded_prompt):
        if _append(str(match.group(1) or "")):
            return out

    for pattern in (_TARGET_ENTITY_LABEL_PATTERN, _TARGET_ENTITY_NAMED_PERSON_PATTERN):
        for match in pattern.finditer(raw):
            if _append(str(match.group(0) or "")):
                return out
    return out


def _extract_target_families(text: str) -> set[str]:
    families: set[str] = set()
    for phrase in _extract_target_phrases(text, limit=16):
        family = _target_family_for_phrase(phrase)
        if family:
            families.add(family)
    folded = _fold_text(text)
    if re.search(r"(?<![a-z0-9])can bo(?![a-z0-9])", folded):
        families.add("person_target")
    if re.search(r"(?<![a-z0-9])quan ly(?![a-z0-9])", folded):
        families.add("person_target")
    if re.search(r"(?<![a-z0-9])truong nhom(?![a-z0-9])", folded):
        families.add("person_target")
    if re.search(r"(?<![a-z0-9])giam doc(?![a-z0-9])", folded):
        families.add("person_target")
    if re.search(r"(?<![a-z0-9])nhan vien(?![a-z0-9])", folded):
        families.add("person_target")
    if re.search(r"(?<![a-z0-9])cong ty(?![a-z0-9])", folded):
        families.add("company_target")
    if re.search(r"(?<![a-z0-9])tap doan(?![a-z0-9])", folded):
        families.add("company_target")
    if re.search(r"(?<![a-z0-9])truong(?![a-z0-9])", folded):
        families.add("school_target")
    if re.search(r"(?<![a-z0-9])bo phan(?![a-z0-9])", folded):
        families.add("org_target")
    if re.search(r"(?<![a-z0-9])phong(?![a-z0-9])", folded):
        families.add("org_target")
    if re.search(r"(?<![a-z0-9])trung tam(?![a-z0-9])", folded):
        families.add("org_target")
    if re.search(r"(?<![a-z0-9])phong ban(?![a-z0-9])", folded):
        families.add("org_target")
    if re.search(r"(?<![a-z0-9])du an(?![a-z0-9])", folded):
        families.add("project_target")
    if re.search(r"(?<![a-z0-9])co van(?![a-z0-9])", folded):
        families.add("person_target")
    if re.search(r"(?<![a-z0-9])tro giang(?![a-z0-9])", folded):
        families.add("person_target")
    if re.search(r"(?<![a-z0-9])giang vien(?![a-z0-9])", folded):
        families.add("person_target")
    return families


def _extract_meaningful_prompt_phrases(prompt: str, *, limit: int = 4) -> list[str]:
    safe_limit = max(1, min(int(limit), 32))
    out: list[str] = []
    seen: set[str] = set()

    for phrase in _extract_target_phrases(prompt, limit=safe_limit):
        normalized = _normalize_phrase_text(phrase)
        folded = _fold_text(normalized)
        if not folded or folded in seen:
            continue
        seen.add(folded)
        out.append(normalized)
        if len(out) >= safe_limit:
            return out

    return out


def _extract_business_noun_phrases(prompt: str, *, limit: int = 4) -> list[str]:
    safe_limit = max(1, min(int(limit), 32))
    folded_prompt = _fold_text(prompt)
    out: list[str] = []
    seen: set[str] = set()

    def _append_phrase(raw_value: str) -> None:
        normalized = _normalize_phrase_text(raw_value)
        normalized = _normalize_phrase_text(
            re.sub(r"(?<![a-z0-9])(.+?)\s+(?:noi|chua)$", r"\1", normalized)
        )
        folded = _fold_text(normalized)
        if not folded or folded in seen:
            return
        if folded in {"thong tin", "thong tin ve", "noi dung", "noi dung ve"}:
            return
        seen.add(folded)
        out.append(normalized)

    def _strip_trailing_generic_modifiers(segment: str) -> str:
        normalized = _normalize_phrase_text(segment)
        while True:
            updated = re.sub(
                r"(?<![a-z0-9])(.+?)\s+(?:noi bo|chua cong bo)$",
                r"\1",
                normalized,
            )
            updated = _normalize_phrase_text(updated)
            if not updated or updated == normalized:
                break
            normalized = updated
        normalized = _normalize_phrase_text(
            re.sub(r"(?<![a-z0-9])(.+?)\s+(?:noi|chua)$", r"\1", normalized)
        )
        return normalized

    candidate_segments = [folded_prompt]
    target_phrases = [_fold_text(value) for value in _extract_target_phrases(prompt, limit=8)]
    for target in target_phrases:
        if not target:
            continue
        scoped_pattern = re.compile(
            rf"(?<![a-z0-9])ve\s+(.+?)(?:\s+cua\s+{re.escape(target)})(?![a-z0-9])"
        )
        for match in scoped_pattern.finditer(folded_prompt):
            segment = _normalize_phrase_text(str(match.group(1) or ""))
            if segment:
                candidate_segments.append(segment)

    for segment in candidate_segments:
        segment = _strip_trailing_generic_modifiers(segment)
        if not segment:
            continue
        for pattern in _BUSINESS_NOUN_PHRASE_PATTERNS:
            for match in pattern.finditer(segment):
                _append_phrase(str(match.group(1) or ""))
                if len(out) >= safe_limit:
                    return out
        for pattern, phrase in _BUSINESS_CONTEXT_QUALIFIER_PATTERNS:
            if pattern.search(segment) is None:
                continue
            _append_phrase(phrase)
            if len(out) >= safe_limit:
                return out
    return out


def _extract_prompt_context_phrases(prompt: str, *, limit: int = 4) -> list[str]:
    safe_limit = max(1, min(int(limit), 32))
    out: list[str] = []
    seen: set[str] = set()
    folded_prompt = _fold_text(prompt)
    for pattern, phrase in _PROMPT_CONTEXT_PHRASE_PATTERNS:
        if re.search(pattern, folded_prompt) is None:
            continue
        normalized = _normalize_phrase_text(phrase)
        folded = _fold_text(normalized)
        if not folded or folded in seen:
            continue
        seen.add(folded)
        out.append(normalized)
        if len(out) >= safe_limit:
            break
    if len(out) < safe_limit:
        for phrase in _extract_business_noun_phrases(prompt, limit=safe_limit):
            normalized = _normalize_phrase_text(phrase)
            folded = _fold_text(normalized)
            if not folded or folded in seen:
                continue
            seen.add(folded)
            out.append(normalized)
            if len(out) >= safe_limit:
                break
    return out


def _prompt_keywords(prompt: str, *, limit: int = 6) -> PromptKeywordBundle:
    safe_limit = max(1, min(int(limit), 32))
    phrases = _extract_meaningful_prompt_phrases(prompt, limit=safe_limit)
    if not phrases:
        phrases = _extract_prompt_context_phrases(prompt, limit=safe_limit)
    phrase_token_set: set[str] = set()
    for phrase in phrases:
        phrase_token_set.update(
            p.strip()
            for p in re.split(r"[^a-zA-Z0-9_]+", _fold_text(phrase))
            if p.strip()
        )

    helper_limit = max(2, min(64, safe_limit * 3))
    helper_tokens: list[str] = []
    seen_tokens: set[str] = set()
    folded = _fold_text(prompt)
    parts = [p.strip() for p in re.split(r"[^a-zA-Z0-9_]+", folded) if p.strip()]
    for part in parts:
        if len(part) < 3:
            continue
        if part in _INSIGHT_STOP_WORDS:
            continue
        if part in phrase_token_set:
            continue
        if part in seen_tokens:
            continue
        seen_tokens.add(part)
        helper_tokens.append(part)
        if len(helper_tokens) >= helper_limit:
            break
    return {"phrases": phrases, "tokens": helper_tokens}


def _phrase_token_count(value: str) -> int:
    return len([token for token in _fold_text(value).split(" ") if token])


def _is_meaningful_phrase(value: str) -> bool:
    normalized = _normalize_phrase_text(value)
    folded = _fold_text(normalized)
    if not folded:
        return False
    if folded in {"thong tin", "noi dung", "ve", "cua"}:
        return False
    if _is_generic_modifier_phrase(normalized) and _phrase_token_count(normalized) <= 2:
        return False
    return _phrase_token_count(normalized) >= 2 or len(folded) >= 8


def _phrase_set_score(values: list[str]) -> tuple[int, int, int]:
    unique_values = _unique_phrase_values(values)
    meaningful_values = [value for value in unique_values if _is_meaningful_phrase(value)]
    max_tokens = max((_phrase_token_count(value) for value in meaningful_values), default=0)
    max_chars = max((len(_normalize_phrase_text(value)) for value in meaningful_values), default=0)
    return (len(meaningful_values), max_tokens, max_chars)


def merge_extraction(
    rule_result: HybridExtractionResult,
    spacy_result: HybridExtractionResult,
) -> HybridExtractionResult:
    target_entities = (
        _unique_phrase_values(rule_result.target_entities)
        if rule_result.target_entities
        else _unique_phrase_values(spacy_result.target_entities)
    )

    rule_business = _unique_phrase_values(rule_result.business_phrases)
    spacy_business = _unique_phrase_values(spacy_result.business_phrases)
    if rule_business:
        business_phrases = rule_business
        if _phrase_set_score(spacy_business) > _phrase_set_score(rule_business):
            business_phrases = spacy_business
    else:
        business_phrases = spacy_business

    context_modifiers = _unique_phrase_values(
        list(rule_result.context_modifiers) + list(spacy_result.context_modifiers)
    )

    return HybridExtractionResult(
        target_entities=target_entities,
        business_phrases=business_phrases,
        context_modifiers=context_modifiers,
        helper_tokens=_unique_phrase_values(rule_result.helper_tokens),
    )


def extract_hybrid(prompt: str) -> HybridExtractionResult:
    keyword_bundle = _prompt_keywords(prompt)
    rule_result = HybridExtractionResult(
        target_entities=_extract_target_phrases(prompt),
        business_phrases=_extract_business_noun_phrases(prompt),
        context_modifiers=_extract_prompt_context_phrases(prompt),
        helper_tokens=list(keyword_bundle["tokens"]),
    )
    if not USE_SPACY_EXTRACTOR:
        logger.debug("suggestion extractor running in rule-only mode")
        return rule_result
    try:
        spacy_result = extract_with_spacy(prompt)
        merged_result = merge_extraction(rule_result, spacy_result)
        logger.debug(
            "suggestion extractor comparison prompt=%r rule_result=%s spacy_result=%s merged_result=%s",
            str(prompt or ""),
            rule_result,
            spacy_result,
            merged_result,
        )
        return merged_result
    except ModuleNotFoundError:
        logger.debug("suggestion spaCy extractor unavailable; using rule-based result")
    except Exception:
        logger.exception(
            "suggestion spaCy extractor failed; continuing with rule-based result"
        )
    return rule_result


def _is_generic_modifier_phrase(value: str) -> bool:
    return _fold_text(value) in _GENERIC_MODIFIER_PHRASES


def _unique_phrase_values(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_phrase_text(value)
        folded = _fold_text(normalized)
        if not folded or folded in seen:
            continue
        seen.add(folded)
        out.append(normalized)
    return out


def _trim_context_phrase_against_keywords(phrase: str, keyword_phrases: list[str]) -> str:
    folded_phrase = _fold_text(phrase)
    if not folded_phrase:
        return ""
    out = folded_phrase
    for keyword in keyword_phrases:
        folded_keyword = _fold_text(keyword)
        if not folded_keyword:
            continue
        pattern = re.compile(
            rf"(?<![a-z0-9])(.+?)\s+(?:ve|cua)\s+{re.escape(folded_keyword)}(?![a-z0-9])$"
        )
        match = pattern.search(out)
        if match is not None:
            out = _normalize_phrase_text(str(match.group(1) or ""))
            continue
        pattern_suffix = re.compile(
            rf"(?<![a-z0-9])(.+?)\s+{re.escape(folded_keyword)}(?![a-z0-9])$"
        )
        suffix_match = pattern_suffix.search(out)
        if suffix_match is not None:
            candidate = _normalize_phrase_text(str(suffix_match.group(1) or ""))
            if candidate:
                out = candidate
    for modifier in _GENERIC_MODIFIER_PHRASES:
        pattern_modifier_suffix = re.compile(
            rf"(?<![a-z0-9])(.+?)\s+{re.escape(modifier)}(?![a-z0-9])$"
        )
        match_modifier = pattern_modifier_suffix.search(out)
        if match_modifier is None:
            continue
        candidate = _normalize_phrase_text(str(match_modifier.group(1) or ""))
        if len([token for token in candidate.split(" ") if token]) >= 2:
            out = candidate
    return _normalize_phrase_text(out)


def _remove_redundant_subphrases(
    phrases: list[str],
    *,
    protected: set[str] | None = None,
) -> list[str]:
    normalized = _unique_phrase_values(phrases)
    if not normalized:
        return []
    protected_folded = {_fold_text(value) for value in (protected or set())}

    out: list[str] = []
    folded_values = [_fold_text(value) for value in normalized]
    for idx, phrase in enumerate(normalized):
        folded = folded_values[idx]
        if not folded:
            continue
        if folded in protected_folded:
            out.append(phrase)
            continue
        token_count = len([token for token in folded.split(" ") if token])
        overshadowed = False
        for jdx, other in enumerate(normalized):
            if jdx == idx:
                continue
            folded_other = folded_values[jdx]
            if not folded_other or folded == folded_other:
                continue
            if folded in folded_other and len(folded_other) > len(folded):
                overshadowed = True
                break
        if overshadowed and token_count <= 4:
            continue
        out.append(phrase)
    return _unique_phrase_values(out)
