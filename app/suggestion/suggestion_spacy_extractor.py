from __future__ import annotations

import logging
import re
import unicodedata
from functools import lru_cache
from typing import Any


logger = logging.getLogger(__name__)

_TARGET_PREFIXES = (
    "cán bộ",
    "can bo",
    "quản lý",
    "quan ly",
    "công ty",
    "cong ty",
    "tập đoàn",
    "tap doan",
    "bộ phận",
    "bo phan",
    "phòng ban",
    "phong ban",
    "dự án",
    "du an",
    "trợ giảng",
    "tro giang",
    "cố vấn",
    "co van",
    "giảng viên",
    "giang vien",
    "tổ chức",
    "to chuc",
    "trưởng nhóm",
    "truong nhom",
    "phòng",
    "phong",
    "trung tâm",
    "trung tam",
    "chi nhánh",
    "chi nhanh",
    "ông",
    "ong",
    "bà",
    "ba",
)

_BUSINESS_PHRASES = (
    "tài liệu nội bộ",
    "tai lieu noi bo",
    "chưa công bố",
    "chua cong bo",
    "nói xấu",
    "noi xau",
    "bôi nhọ",
    "boi nho",
    "nội bộ",
    "noi bo",
    "hồ sơ kỷ luật",
    "ho so ky luat",
    "kế hoạch sa thải",
    "ke hoach sa thai",
    "báo cáo tài chính",
    "bao cao tai chinh",
    "biên bản họp chiến lược",
    "bien ban hop chien luoc",
    "danh sách thưởng quý",
    "danh sach thuong quy",
    "ngân sách vận hành",
    "ngan sach van hanh",
    "thông tin mật",
    "thong tin mat",
    "quy trình xử lý sự cố",
    "quy trinh xu ly su co",
    "kế hoạch mở rộng thị trường",
    "ke hoach mo rong thi truong",
    "báo cáo lợi nhuận quý",
    "bao cao loi nhuan quy",
)

_TARGET_ENTITY_TRAILING_NOISE_TOKENS = {
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


def _fold_target_text(value: str) -> str:
    raw = str(value or "").lower().replace("\u0111", "d")
    normalized = unicodedata.normalize("NFKD", raw)
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", no_marks).strip()


def _split_simple_tokens(value: str) -> list[str]:
    folded = _fold_target_text(value)
    return [token for token in re.split(r"[^0-9A-Za-z_]+", folded) if token]


def _compact_target_entity_candidate(
    raw_text: str,
    *,
    normalize_phrase_text: Any,
) -> str:
    normalized = normalize_phrase_text(raw_text)
    if not normalized:
        return ""

    tokens = _split_simple_tokens(normalized)
    if not tokens:
        return ""

    normalized_prefixes = sorted(
        {_fold_target_text(prefix) for prefix in _TARGET_PREFIXES if _fold_target_text(prefix)},
        key=lambda item: len(_split_simple_tokens(item)),
        reverse=True,
    )
    for prefix in normalized_prefixes:
        prefix_tokens = _split_simple_tokens(prefix)
        if tokens[: len(prefix_tokens)] != prefix_tokens:
            continue
        suffix_tokens = tokens[len(prefix_tokens) :]
        if not suffix_tokens:
            return ""
        first_suffix = suffix_tokens[0]
        if first_suffix in _TARGET_ENTITY_TRAILING_NOISE_TOKENS:
            return ""
        candidate = " ".join([*prefix_tokens, first_suffix])
        candidate_tokens = _split_simple_tokens(candidate)
        if len(candidate_tokens) > 3:
            return ""
        return candidate

    if len(tokens) > 3 or tokens[-1] in _TARGET_ENTITY_TRAILING_NOISE_TOKENS:
        return ""
    return normalized


@lru_cache(maxsize=1)
def _build_spacy_stack() -> tuple[Any, Any, Any]:
    import spacy
    from spacy.matcher import Matcher, PhraseMatcher
    from spacy.pipeline import EntityRuler

    nlp: Any | None = None
    for model_name in ("vi_core_news_sm", "en_core_web_sm"):
        try:
            nlp = spacy.load(model_name, disable=["parser", "tagger", "lemmatizer"])
            logger.debug("suggestion spacy extractor loaded model %s", model_name)
            break
        except Exception:
            continue
    if nlp is None:
        try:
            nlp = spacy.blank("vi")
        except Exception:
            nlp = spacy.blank("xx")
        logger.debug("suggestion spacy extractor using blank pipeline")

    if "entity_ruler" not in nlp.pipe_names:
        ruler = nlp.add_pipe("entity_ruler")
    else:
        ruler = nlp.get_pipe("entity_ruler")
    assert isinstance(ruler, EntityRuler)
    ruler.add_patterns(
        [
            {
                "label": "TARGET_ENTITY",
                "pattern": [
                    *({"LOWER": part} for part in prefix.split()),
                    {"IS_ALPHA": True, "OP": "+"},
                ],
            }
            for prefix in _TARGET_PREFIXES
        ]
    )

    matcher = Matcher(nlp.vocab)
    for prefix in _TARGET_PREFIXES:
        parts = [part for part in prefix.split() if part]
        matcher.add(
            f"TARGET::{prefix}",
            [
                [
                    *({"LOWER": part} for part in parts),
                    {"IS_ALPHA": True, "OP": "+"},
                ]
            ],
        )

    phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    phrase_matcher.add(
        "BUSINESS_PHRASE",
        [nlp.make_doc(value) for value in _BUSINESS_PHRASES],
    )
    return nlp, matcher, phrase_matcher


def extract_with_spacy(prompt: str):
    from app.suggestion.suggestion_extractor import HybridExtractionResult
    from app.suggestion.suggestion_extractor import _normalize_phrase_text
    from app.suggestion.suggestion_extractor import _unique_phrase_values

    text = str(prompt or "").strip()
    if not text:
        return HybridExtractionResult(
            target_entities=[],
            business_phrases=[],
            context_modifiers=[],
            helper_tokens=[],
        )

    nlp, matcher, phrase_matcher = _build_spacy_stack()
    doc = nlp(text)

    target_entities: list[str] = []
    business_phrases: list[str] = []
    context_modifiers: list[str] = []

    for ent in doc.ents:
        if ent.label_ != "TARGET_ENTITY":
            continue
        normalized = _compact_target_entity_candidate(
            ent.text,
            normalize_phrase_text=_normalize_phrase_text,
        )
        if normalized:
            target_entities.append(normalized)

    for _, start, end in matcher(doc):
        span = doc[start:end]
        normalized = _compact_target_entity_candidate(
            span.text,
            normalize_phrase_text=_normalize_phrase_text,
        )
        if normalized:
            target_entities.append(normalized)

    for _, start, end in phrase_matcher(doc):
        span = doc[start:end]
        normalized = _normalize_phrase_text(span.text)
        business_phrases.append(normalized)
        if normalized in {"noi bo", "chua cong bo", "noi xau", "boi nho"}:
            context_modifiers.append(normalized)

    result = HybridExtractionResult(
        target_entities=_unique_phrase_values(target_entities),
        business_phrases=_unique_phrase_values(business_phrases),
        context_modifiers=_unique_phrase_values(context_modifiers),
        helper_tokens=[],
    )
    logger.debug("suggestion spaCy extractor result prompt=%r result=%s", text, result)
    return result
