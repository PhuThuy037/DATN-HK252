from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

_SEPARATORS = "-_./:#@$"
_TOKEN_SCAN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-_./:#@$]{1,63}")
_EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?84|0)\d{9,10}(?!\d)")
_TAX_ID_PATTERN = re.compile(r"(?<!\d)\d{10}(?:-\d{3})?(?!\d)")
_CCCD_PATTERN = re.compile(r"(?<!\d)\d{12}(?!\d)")
_VERSION_SEGMENT_PATTERN = re.compile(r"^v\d{1,3}$", re.IGNORECASE)

_LITERAL_INTENT_KEYWORDS = (
    "ma",
    "code",
    "key",
    "token",
    "secret",
    "noi bo",
    "internal",
    "identifier",
    "id",
)
_CCCD_KEYWORDS = ("cccd", "cmnd", "can cuoc")
_TAX_ID_KEYWORDS = ("tax", "tax id", "tax code", "mst", "ma so thue", "tin")
_PHONE_KEYWORDS = ("phone", "sdt", "so dien thoai", "hotline")
_EMAIL_KEYWORDS = ("email", "mail", "e-mail", "gmail")

_TECHNICAL_SEGMENTS = {
    "api",
    "auth",
    "client",
    "db",
    "dev",
    "env",
    "id",
    "key",
    "module",
    "prod",
    "secret",
    "server",
    "svc",
    "token",
    "uid",
    "gid",
    "stg",
    "stage",
    "v1",
    "v2",
    "v3",
}
_COMMON_WORD_SEGMENTS = {
    "please",
    "check",
    "this",
    "that",
    "allow",
    "block",
    "mask",
    "hide",
    "show",
    "with",
    "from",
    "your",
    "mine",
    "ours",
    "the",
    "and",
}
_CANDIDATE_STOPWORDS = {
    "che",
    "an",
    "mask",
    "block",
    "tao",
    "toi",
    "muon",
    "nay",
    "ma",
    "code",
}

_INTERNAL_SCORE_THRESHOLD = 0.62
_AMBIGUOUS_SCORE_THRESHOLD = 0.45
_CANDIDATE_SCORE_THRESHOLD = 0.32


@dataclass(frozen=True)
class TokenCandidate:
    raw: str
    normalized: str
    segments: tuple[str, ...]
    separators: tuple[str, ...]
    has_alpha: bool
    has_digit: bool
    has_upper: bool

    @property
    def separator_count(self) -> int:
        return sum(1 for ch in self.raw if ch in _SEPARATORS)


@dataclass(frozen=True)
class LiteralDetectionResult:
    intent_literal: bool
    known_pii_type: str | None
    decision_hint: str
    top_token: str | None
    token_score: float
    candidate_tokens: tuple[str, ...]
    ambiguous_tokens: tuple[str, ...]

    @property
    def is_known_pii(self) -> bool:
        return self.known_pii_type is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "intent_literal": self.intent_literal,
            "known_pii_type": self.known_pii_type,
            "is_known_pii": self.is_known_pii,
            "decision_hint": self.decision_hint,
            "top_token": self.top_token,
            "token_score": self.token_score,
            "candidate_tokens": list(self.candidate_tokens),
            "ambiguous_tokens": list(self.ambiguous_tokens),
        }


def _fold_text(value: str) -> str:
    raw = str(value or "").lower().replace("\u0111", "d")
    normalized = unicodedata.normalize("NFKD", raw)
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", no_marks).strip()


def _contains_keyword(folded_prompt: str, keyword: str) -> bool:
    normalized_keyword = _fold_text(keyword)
    if not normalized_keyword:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
    return re.search(pattern, folded_prompt) is not None


def _contains_any_keyword(folded_prompt: str, keywords: tuple[str, ...]) -> bool:
    return any(_contains_keyword(folded_prompt, keyword) for keyword in keywords)


def _looks_candidate_term(token: str) -> bool:
    raw = str(token or "").strip()
    if len(raw) < 3:
        return False

    normalized = _fold_text(raw)
    if not normalized:
        return False
    if normalized in _CANDIDATE_STOPWORDS:
        return False

    has_separator = any(ch in _SEPARATORS for ch in raw)
    has_alpha = bool(re.search(r"[a-zA-Z]", raw))
    has_digit = bool(re.search(r"\d", raw))
    has_upper = any(ch.isupper() for ch in raw)
    if has_separator:
        return True
    if has_alpha and has_digit:
        return True
    if has_upper and len(raw) >= 4:
        return True
    return len(raw) >= 8


def _clean_candidate(token: str) -> str:
    cleaned = str(token or "").strip()
    while cleaned and cleaned[0] in _SEPARATORS:
        cleaned = cleaned[1:]
    while cleaned and cleaned[-1] in _SEPARATORS:
        cleaned = cleaned[:-1]
    return cleaned


def _build_candidate(token: str) -> TokenCandidate | None:
    raw = _clean_candidate(token)
    if not _looks_candidate_term(raw):
        return None
    if len(raw) > 64:
        return None

    normalized = _fold_text(raw)
    if not normalized:
        return None

    segments = tuple(part for part in re.split(r"[-_./:#@$]+", raw) if part)
    if not segments:
        return None

    separators = tuple(ch for ch in raw if ch in _SEPARATORS)
    has_alpha = bool(re.search(r"[a-zA-Z]", raw))
    has_digit = bool(re.search(r"\d", raw))
    has_upper = any(ch.isupper() for ch in raw)
    return TokenCandidate(
        raw=raw,
        normalized=normalized,
        segments=segments,
        separators=separators,
        has_alpha=has_alpha,
        has_digit=has_digit,
        has_upper=has_upper,
    )


def _segment_entropy(value: str) -> float:
    text = re.sub(r"[^a-z0-9]+", "", _fold_text(value))
    if len(text) <= 1:
        return 0.0
    counts = Counter(text)
    total = float(len(text))
    entropy = 0.0
    for count in counts.values():
        probability = float(count) / total
        entropy -= probability * math.log2(probability)
    return entropy


def _score_candidate(candidate: TokenCandidate, *, intent_literal: bool) -> float:
    raw = candidate.raw
    normalized = candidate.normalized
    segments = candidate.segments
    segment_count = len(segments)
    separator_count = candidate.separator_count
    unique_separators = set(candidate.separators)
    length = len(normalized)

    score = 0.0
    if 6 <= length <= 40:
        score += 0.12
    elif 4 <= length <= 64:
        score += 0.06

    if separator_count >= 1:
        score += 0.18
    if separator_count >= 2:
        score += 0.08
    if len(unique_separators) >= 2:
        score += 0.04

    if 2 <= segment_count <= 5:
        score += 0.12
    elif segment_count > 5:
        score += 0.05

    if any(len(part) >= 3 for part in segments):
        score += 0.05
    if separator_count >= 1 and all(2 <= len(part) <= 16 for part in segments):
        score += 0.12

    if candidate.has_alpha and candidate.has_digit:
        score += 0.16
    elif candidate.has_digit:
        score += 0.08

    if candidate.has_upper:
        score += 0.08

    if _VERSION_SEGMENT_PATTERN.search(raw):
        score += 0.08
    if any(ch in raw for ch in ("#", "@", "$")):
        score += 0.03

    technical_hits = sum(1 for part in segments if _fold_text(part) in _TECHNICAL_SEGMENTS)
    if technical_hits >= 1:
        score += 0.12
    if technical_hits >= 2:
        score += 0.08

    if all(len(part) == 1 for part in segments):
        score -= 0.22

    all_alpha_lower = (
        all(part.isalpha() and part.islower() for part in segments) and not candidate.has_digit
    )
    if all_alpha_lower and segment_count >= 2:
        score -= 0.07

    if "@" in raw and (not candidate.has_digit):
        score -= 0.48
    if "$" in raw and segment_count <= 2:
        score -= 0.40
    if "#" in raw and segment_count <= 2 and (not candidate.has_digit):
        score -= 0.05

    if all_alpha_lower and segment_count >= 2:
        folded_segments = {_fold_text(part) for part in segments}
        if folded_segments and folded_segments.issubset(_COMMON_WORD_SEGMENTS):
            score -= 0.30

    if _segment_entropy(raw) < 1.30:
        score -= 0.08

    if intent_literal:
        score += 0.15
        if separator_count >= 1 and segment_count >= 2:
            score += 0.06

    return max(0.0, min(1.0, round(score, 4)))


def _extract_candidates(prompt: str, *, limit: int = 12) -> tuple[TokenCandidate, ...]:
    raw = str(prompt or "")
    out: list[TokenCandidate] = []
    seen: set[str] = set()
    safe_limit = max(1, min(int(limit), 32))

    for match in _TOKEN_SCAN_PATTERN.finditer(raw):
        token = _build_candidate(str(match.group(0) or ""))
        if token is None:
            continue
        key = token.normalized.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
        if len(out) >= safe_limit:
            break
    return tuple(out)


def _infer_known_pii_type(prompt: str) -> str | None:
    raw = str(prompt or "")
    folded = _fold_text(prompt)
    if not folded:
        return None

    if _contains_any_keyword(folded, _CCCD_KEYWORDS):
        return "CCCD"
    if _contains_any_keyword(folded, _TAX_ID_KEYWORDS):
        return "TAX_ID"
    if _contains_any_keyword(folded, _PHONE_KEYWORDS):
        return "PHONE"
    if _contains_any_keyword(folded, _EMAIL_KEYWORDS):
        return "EMAIL"

    if _EMAIL_PATTERN.search(raw):
        return "EMAIL"
    if _TAX_ID_PATTERN.search(raw):
        return "TAX_ID"
    if _PHONE_PATTERN.search(raw):
        return "PHONE"
    if _CCCD_PATTERN.search(raw):
        return "CCCD"
    return None


def _has_literal_intent(prompt: str) -> bool:
    folded = _fold_text(prompt)
    if not folded:
        return False
    return _contains_any_keyword(folded, _LITERAL_INTENT_KEYWORDS)


@lru_cache(maxsize=2048)
def analyze_literal_prompt(prompt: str, *, limit: int = 8) -> LiteralDetectionResult:
    intent_literal = _has_literal_intent(prompt)
    known_pii_type = _infer_known_pii_type(prompt)
    candidates = _extract_candidates(prompt, limit=max(1, int(limit)))

    scored: list[tuple[float, TokenCandidate]] = []
    for candidate in candidates:
        score = _score_candidate(candidate, intent_literal=intent_literal)
        scored.append((score, candidate))
    scored.sort(key=lambda item: (item[0], len(item[1].normalized)), reverse=True)

    candidate_tokens = tuple(
        candidate.normalized.upper()
        for score, candidate in scored
        if score >= _CANDIDATE_SCORE_THRESHOLD
    )
    ambiguous_tokens = tuple(
        candidate.normalized.upper()
        for score, candidate in scored
        if _AMBIGUOUS_SCORE_THRESHOLD <= score < _INTERNAL_SCORE_THRESHOLD
    )

    top_token: str | None = None
    top_score = 0.0
    if scored:
        top_score, top_candidate = scored[0]
        top_token = top_candidate.normalized.upper()

    if known_pii_type:
        decision_hint = known_pii_type
    elif intent_literal and top_token and top_score >= _INTERNAL_SCORE_THRESHOLD:
        decision_hint = "INTERNAL_CODE"
    elif top_score >= _AMBIGUOUS_SCORE_THRESHOLD:
        decision_hint = "AMBIGUOUS"
    elif intent_literal:
        decision_hint = "AMBIGUOUS"
    else:
        decision_hint = "AMBIGUOUS"

    return LiteralDetectionResult(
        intent_literal=bool(intent_literal),
        known_pii_type=known_pii_type,
        decision_hint=decision_hint,
        top_token=top_token,
        token_score=float(top_score),
        candidate_tokens=candidate_tokens[: max(1, int(limit))],
        ambiguous_tokens=ambiguous_tokens[: max(1, int(limit))],
    )


def score_identifier_token(token: str) -> float:
    candidate = _build_candidate(token)
    if candidate is None:
        return 0.0
    return _score_candidate(candidate, intent_literal=False)
