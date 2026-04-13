from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.suggestion import service as suggestion_service
from app.suggestion import suggestion_generation, suggestion_spacy_extractor
from app.suggestion.literal_detector import LiteralDetectionResult
from app.suggestion.suggestion_extractor import HybridExtractionResult


def _extract_first_context_keyword_any_of(draft: object) -> list[str]:
    conditions = getattr(draft, "rule").conditions  # type: ignore[attr-defined]
    all_nodes = []
    if isinstance(conditions, dict):
        raw_nodes = conditions.get("all")
        if isinstance(raw_nodes, list):
            all_nodes = raw_nodes
    for node in all_nodes:
        if not isinstance(node, dict):
            continue
        signal = node.get("signal")
        if not isinstance(signal, dict):
            continue
        if str(signal.get("field") or "").strip().lower() != "context_keywords":
            continue
        any_of = signal.get("any_of")
        if isinstance(any_of, list):
            return [str(value or "") for value in any_of]
    return []


def _extract_all_context_keyword_any_of(draft: object) -> list[list[str]]:
    conditions = getattr(draft, "rule").conditions  # type: ignore[attr-defined]
    rows: list[list[str]] = []
    all_nodes = []
    if isinstance(conditions, dict):
        raw_nodes = conditions.get("all")
        if isinstance(raw_nodes, list):
            all_nodes = raw_nodes
    for node in all_nodes:
        if not isinstance(node, dict):
            continue
        signal = node.get("signal")
        if not isinstance(signal, dict):
            continue
        if str(signal.get("field") or "").strip().lower() != "context_keywords":
            continue
        any_of = signal.get("any_of")
        if isinstance(any_of, list):
            rows.append([str(value or "") for value in any_of])
    return rows


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("Phòng K", "phong k"),
        ("Phòng T", "phong t"),
        ("truong nhom q lam viec ngu nhu cho", "truong nhom q"),
        ("phong k", "phong k"),
        ("trung tam m", "trung tam m"),
        ("cong ty z", "cong ty z"),
    ],
)
def test_spacy_target_entity_compaction_keeps_short_target_and_trims_long_span(
    raw_value: str,
    expected: str,
) -> None:
    normalized = suggestion_spacy_extractor._compact_target_entity_candidate(
        raw_value,
        normalize_phrase_text=suggestion_service._normalize_phrase_text,  # type: ignore[attr-defined]
    )
    assert suggestion_service._fold_text(normalized) == expected  # type: ignore[attr-defined]


def test_generation_prefers_clean_target_phrase_over_dirty_sentence_keyword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt = "toi muon chan cac noi dung noi xau ve truong nhom q"

    class _FakeRetriever:
        def __init__(self, *, session: object, company_id: UUID) -> None:
            _ = (session, company_id)

        def retrieve_policy_chunks(
            self,
            _prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return []

        def retrieve_related_rules(
            self,
            _prompt: str,
            user_id: UUID,
            top_k: int = 8,
            extraction: HybridExtractionResult | None = None,
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k, extraction)
            return []

    def _fake_generate_with_llm(
        _prompt: str,
        *,
        extraction: HybridExtractionResult | None,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (
            extraction,
            prompt_keyword_bundle,
            policy_chunks,
            rule_references,
            literal_detection,
        )
        payload = {
            "rule": {
                "stable_key": "personal.custom.spacy.guard",
                "name": "spacy guard",
                "description": "prevent dirty sentence keyword",
                "scope": "chat",
                "conditions": {
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["truong nhom q lam viec ngu nhu cho", "noi xau"],
                            }
                        }
                    ]
                },
                "action": "block",
                "severity": "high",
                "priority": 90,
                "match_mode": "strict_keyword",
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "noi xau",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                }
            ],
        }
        draft = suggestion_service.RuleSuggestionDraftPayload.model_validate(payload)  # type: ignore[attr-defined]
        return draft, {
            "source": "llm",
            "provider": "mock",
            "model": "mock-model",
            "fallback_used": False,
        }

    monkeypatch.setattr(suggestion_generation, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_generation, "_generate_with_llm", _fake_generate_with_llm)
    monkeypatch.setattr(
        suggestion_generation,
        "extract_hybrid",
        lambda _prompt: HybridExtractionResult(
            target_entities=["truong nhom q"],
            business_phrases=[],
            context_modifiers=["noi xau"],
            helper_tokens=[],
        ),
    )

    draft, _meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt=prompt,
    )

    folded_keywords = {
        suggestion_service._fold_text(value)  # type: ignore[attr-defined]
        for value in _extract_first_context_keyword_any_of(draft)
    }
    assert "truong nhom q" in folded_keywords
    assert "truong nhom q lam viec ngu nhu cho" not in folded_keywords


@pytest.mark.parametrize(
    ("prompt", "expected_keyword", "expected_context_terms"),
    [
        (
            "tôi muốn chặn thông tin về Phòng K",
            {"phong k"},
            set(),
        ),
        (
            "tôi muốn chặn các nội dung nói xấu về Trưởng nhóm Q",
            {"truong nhom q"},
            {"noi xau"},
        ),
        (
            "tôi muốn chặn các nội dung về tài liệu nội bộ của Trung tâm M",
            {"trung tam m"},
            {"tai lieu noi bo"},
        ),
        (
            "tôi muốn chặn các nội dung về kế hoạch mở rộng thị trường nội bộ của Công ty Z",
            {"cong ty z"},
            {"ke hoach mo rong thi truong", "noi bo"},
        ),
        (
            "tôi muốn chặn thông tin mật của Phòng T",
            {"phong t"},
            {"thong tin mat"},
        ),
    ],
)
def test_generation_keeps_target_entity_as_keyword_and_business_phrase_as_context(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    expected_keyword: set[str],
    expected_context_terms: set[str],
) -> None:
    class _FakeRetriever:
        def __init__(self, *, session: object, company_id: UUID) -> None:
            _ = (session, company_id)

        def retrieve_policy_chunks(
            self,
            _prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return []

        def retrieve_related_rules(
            self,
            _prompt: str,
            user_id: UUID,
            top_k: int = 8,
            extraction: HybridExtractionResult | None = None,
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k, extraction)
            return []

    def _fake_generate_with_llm(
        _prompt: str,
        *,
        extraction: HybridExtractionResult | None,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (
            extraction,
            prompt_keyword_bundle,
            policy_chunks,
            rule_references,
            literal_detection,
        )
        payload = {
            "rule": {
                "stable_key": "personal.custom.role.split.guard",
                "name": "role split guard",
                "description": "keep target entity in keyword",
                "scope": "chat",
                "conditions": {
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["tai lieu noi bo", "noi xau", "thong tin mat", "noi bo"],
                            }
                        }
                    ]
                },
                "action": "block",
                "severity": "high",
                "priority": 90,
                "match_mode": "strict_keyword",
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [],
        }
        draft = suggestion_service.RuleSuggestionDraftPayload.model_validate(payload)  # type: ignore[attr-defined]
        return draft, {
            "source": "llm",
            "provider": "mock",
            "model": "mock-model",
            "fallback_used": False,
        }

    monkeypatch.setattr(suggestion_generation, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_generation, "_generate_with_llm", _fake_generate_with_llm)

    draft, _meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt=prompt,
    )

    folded_keywords = {
        suggestion_service._fold_text(value)  # type: ignore[attr-defined]
        for value in _extract_first_context_keyword_any_of(draft)
    }
    assert folded_keywords == expected_keyword

    folded_context_terms = {
        suggestion_service._fold_text(str(getattr(term, "term", "") or ""))  # type: ignore[attr-defined]
        for term in list(getattr(draft, "context_terms", []) or [])
        if str(getattr(term, "term", "") or "").strip()
    }
    if expected_context_terms:
        assert expected_context_terms.issubset(folded_context_terms)
    else:
        assert folded_context_terms == set()
    assert folded_keywords.isdisjoint(folded_context_terms)


@pytest.mark.parametrize(
    ("prompt", "expected_condition_terms"),
    [
        (
            "tÃ´i muá»‘n cháº·n cÃ¡c ná»™i dung nÃ³i xáº¥u vá» TrÆ°á»Ÿng nhÃ³m Q",
            {"truong nhom q", "noi xau"},
        ),
        (
            "tÃ´i muá»‘n cháº·n cÃ¡c ná»™i dung vá» tÃ i liá»‡u ná»™i bá»™ cá»§a Trung tÃ¢m M",
            {"trung tam m", "tai lieu noi bo"},
        ),
    ],
)
def test_generation_builds_semantic_and_conditions_from_target_and_topic(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    expected_condition_terms: set[str],
) -> None:
    class _FakeRetriever:
        def __init__(self, *, session: object, company_id: UUID) -> None:
            _ = (session, company_id)

        def retrieve_policy_chunks(
            self,
            _prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return []

        def retrieve_related_rules(
            self,
            _prompt: str,
            user_id: UUID,
            top_k: int = 8,
            extraction: HybridExtractionResult | None = None,
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k, extraction)
            return []

    def _fake_generate_with_llm(
        _prompt: str,
        *,
        extraction: HybridExtractionResult | None,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (
            extraction,
            prompt_keyword_bundle,
            policy_chunks,
            rule_references,
            literal_detection,
        )
        payload = {
            "rule": {
                "stable_key": "personal.custom.semantic.and.guard",
                "name": "semantic and guard",
                "description": "build AND conditions from target and topic",
                "scope": "chat",
                "conditions": {
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["truong nhom q", "tai lieu noi bo", "noi xau"],
                            }
                        }
                    ]
                },
                "action": "block",
                "severity": "high",
                "priority": 90,
                "match_mode": "keyword_plus_semantic",
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [],
        }
        draft = suggestion_service.RuleSuggestionDraftPayload.model_validate(payload)  # type: ignore[attr-defined]
        return draft, {
            "source": "llm",
            "provider": "mock",
            "model": "mock-model",
            "fallback_used": False,
        }

    monkeypatch.setattr(suggestion_generation, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_generation, "_generate_with_llm", _fake_generate_with_llm)

    draft, _meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt=prompt,
    )

    folded_rows = {
        tuple(
            suggestion_service._fold_text(value)  # type: ignore[attr-defined]
            for value in row
        )
        for row in _extract_all_context_keyword_any_of(draft)
    }
    flattened = {value for row in folded_rows for value in row}
    assert expected_condition_terms.issubset(flattened)
    assert len(folded_rows) >= 2


@pytest.mark.parametrize(
    ("prompt", "expected_keyword", "expected_context_terms", "forbidden_context_terms"),
    [
        (
            "tôi muốn chặn các nội dung về danh sách thưởng quý chưa công bố của Bộ phận P",
            {"bo phan p"},
            {"danh sach thuong quy", "chua cong bo"},
            {"danh sach thuong quy chua"},
        ),
        (
            "tôi muốn chặn các nội dung về biên bản họp chiến lược nội bộ của Trung tâm S",
            {"trung tam s"},
            {"bien ban hop chien luoc", "noi bo"},
            {"bien ban hop chien luoc noi"},
        ),
    ],
)
def test_generation_trims_truncated_context_phrase_before_modifier_tail(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    expected_keyword: set[str],
    expected_context_terms: set[str],
    forbidden_context_terms: set[str],
) -> None:
    class _FakeRetriever:
        def __init__(self, *, session: object, company_id: UUID) -> None:
            _ = (session, company_id)

        def retrieve_policy_chunks(
            self,
            _prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return []

        def retrieve_related_rules(
            self,
            _prompt: str,
            user_id: UUID,
            top_k: int = 8,
            extraction: HybridExtractionResult | None = None,
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k, extraction)
            return []

    def _fake_generate_with_llm(
        _prompt: str,
        *,
        extraction: HybridExtractionResult | None,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (
            extraction,
            prompt_keyword_bundle,
            policy_chunks,
            rule_references,
            literal_detection,
        )
        payload = {
            "rule": {
                "stable_key": "personal.custom.context.tail.guard",
                "name": "context tail guard",
                "description": "trim truncated context phrases",
                "scope": "chat",
                "conditions": {
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["tai lieu noi bo", "noi bo", "chua cong bo"],
                            }
                        }
                    ]
                },
                "action": "block",
                "severity": "high",
                "priority": 90,
                "match_mode": "strict_keyword",
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [],
        }
        draft = suggestion_service.RuleSuggestionDraftPayload.model_validate(payload)  # type: ignore[attr-defined]
        return draft, {
            "source": "llm",
            "provider": "mock",
            "model": "mock-model",
            "fallback_used": False,
        }

    monkeypatch.setattr(suggestion_generation, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_generation, "_generate_with_llm", _fake_generate_with_llm)

    draft, _meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt=prompt,
    )

    folded_keywords = {
        suggestion_service._fold_text(value)  # type: ignore[attr-defined]
        for value in _extract_first_context_keyword_any_of(draft)
    }
    assert folded_keywords == expected_keyword

    folded_context_terms = {
        suggestion_service._fold_text(str(getattr(term, "term", "") or ""))  # type: ignore[attr-defined]
        for term in list(getattr(draft, "context_terms", []) or [])
        if str(getattr(term, "term", "") or "").strip()
    }
    assert expected_context_terms.issubset(folded_context_terms)
    for forbidden in forbidden_context_terms:
        assert forbidden not in folded_context_terms
