from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity
from app.suggestion import service as suggestion_service
from app.suggestion.literal_detector import (
    LiteralDetectionResult,
    analyze_literal_prompt,
)


def _make_rule_row(
    *,
    stable_key: str,
    name: str,
    description: str,
    priority: int = 80,
    company_id: UUID | None = None,
) -> object:
    return SimpleNamespace(
        id=uuid4(),
        company_id=company_id,
        stable_key=stable_key,
        name=name,
        description=description,
        scope=RuleScope.prompt,
        action=RuleAction.block,
        severity=RuleSeverity.high,
        priority=priority,
        rag_mode=RagMode.off,
        conditions={
            "all": [
                {
                    "signal": {
                        "field": "context_keywords",
                        "any_of": [description.lower()],
                    }
                }
            ]
        },
    )


class _FakeExecResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)


class _FakeSession:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def exec(self, _statement: object) -> _FakeExecResult:
        return _FakeExecResult(self._rows)


def test_phase_a_literal_detector_does_not_map_thong_tin_to_tax_id() -> None:
    detected = analyze_literal_prompt("tôi muốn chặn thông tin về Cán bộ X", limit=8)
    assert detected.known_pii_type is None
    assert detected.decision_hint != "TAX_ID"


@pytest.mark.parametrize(
    ("prompt", "expected_phrase", "forbidden_phrases"),
    [
        (
            "tôi muốn chặn thông tin về Cán bộ X",
            "cán bộ x",
            ("công ty x", "trường x"),
        ),
        ("tôi muốn chặn thông tin về Công ty X", "công ty x", tuple()),
        ("tôi muốn chặn thông tin về Trường X", "trường x", tuple()),
        ("tôi muốn chặn thông tin về Ông A", "ông a", tuple()),
    ],
)
def test_phase_a_prompt_keywords_keep_target_phrase(
    prompt: str,
    expected_phrase: str,
    forbidden_phrases: tuple[str, ...],
) -> None:
    keyword_bundle = suggestion_service._prompt_keywords(prompt, limit=12)  # type: ignore[attr-defined]
    lowered_phrases = [str(item).lower() for item in keyword_bundle["phrases"]]
    assert expected_phrase in lowered_phrases
    for forbidden in forbidden_phrases:
        assert forbidden not in lowered_phrases


def test_phase_a_rule_references_prefer_same_target_family() -> None:
    company_id = uuid4()
    session = _FakeSession(
        [
            _make_rule_row(
                stable_key="personal.custom.cong_ty_x",
                name="Cong Ty X Internal Docs",
                description="công ty x tài liệu nội bộ",
                priority=120,
                company_id=company_id,
            ),
            _make_rule_row(
                stable_key="personal.custom.can_bo_x",
                name="Can Bo X Sensitive Profile",
                description="cán bộ x thông tin cá nhân",
                priority=60,
                company_id=company_id,
            ),
            _make_rule_row(
                stable_key="personal.custom.truong_x",
                name="Truong X Internal Memo",
                description="trường x tài liệu nội bộ",
                priority=110,
                company_id=company_id,
            ),
        ]
    )

    refs = suggestion_service._build_rule_references(  # type: ignore[attr-defined]
        session=session,
        company_id=company_id,
        prompt="tôi muốn chặn thông tin về Cán bộ X",
        limit=3,
    )
    assert refs
    assert refs[0]["stable_key"] == "personal.custom.can_bo_x"
    assert all(
        row["stable_key"] != "personal.custom.cong_ty_x" for row in refs[1:]
    )


def test_phase_a_generate_with_llm_prompt_has_target_phrase_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def _fake_generate_text_sync(
        *, prompt: str, system_prompt: str, provider: str
    ) -> object:
        _ = provider
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        payload = {
            "rule": {
                "stable_key": "personal.custom.suggested.phasea",
                "name": "Suggested phase A draft",
                "description": "generated for phase A validation",
                "scope": "prompt",
                "conditions": {
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["cán bộ x"],
                            }
                        }
                    ]
                },
                "action": "block",
                "severity": "high",
                "priority": 80,
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [
                {
                    "entity_type": "INTERNAL_CODE",
                    "term": "cán bộ x",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                }
            ],
        }
        return SimpleNamespace(
            text=json.dumps(payload, ensure_ascii=False),
            provider="mock",
            model="mock-model",
            fallback_used=False,
        )

    monkeypatch.setattr(suggestion_service, "generate_text_sync", _fake_generate_text_sync)
    literal_detection = LiteralDetectionResult(
        intent_literal=False,
        known_pii_type=None,
        decision_hint="AMBIGUOUS",
        top_token=None,
        token_score=0.0,
        candidate_tokens=tuple(),
        ambiguous_tokens=tuple(),
    )

    draft, meta = suggestion_service._generate_with_llm(  # type: ignore[attr-defined]
        "tôi muốn chặn thông tin về Cán bộ X",
        prompt_keyword_bundle={
            "phrases": ["cán bộ x"],
            "tokens": ["thông", "tin", "chặn"],
        },
        policy_chunks=[],
        rule_references=[
            {
                "rule_id": "r1",
                "stable_key": "personal.custom.cong_ty_x",
                "name": "Cong Ty X Internal Docs",
            }
        ],
        literal_detection=literal_detection,
    )

    assert draft.context_terms
    assert str(draft.context_terms[0].term).lower() == "cán bộ x"
    assert meta["source"] == "llm"
    prompt_body = captured["prompt"].lower()
    assert "target phrases to preserve verbatim" in prompt_body
    assert "helper tokens for retrieval/context only" in prompt_body
    assert "cán bộ x" in prompt_body
    assert "do not rewrite person-target phrases into company/school/organization-like labels" in prompt_body


def test_phase_a_prompt_keyword_bundle_separates_phrase_and_helper_tokens() -> None:
    bundle = suggestion_service._prompt_keywords(  # type: ignore[attr-defined]
        "tôi muốn chặn thông tin về Công ty X",
        limit=12,
    )
    folded_phrases = {
        suggestion_service._fold_text(str(value))  # type: ignore[attr-defined]
        for value in bundle["phrases"]
    }
    helper_tokens = {str(value).strip().lower() for value in bundle["tokens"]}
    assert "cong ty x" in folded_phrases
    assert "muon" in helper_tokens
    assert "thong" in helper_tokens
    assert "tin" in helper_tokens
    assert "cong" not in helper_tokens
    assert "ty" not in helper_tokens


def test_phase_a_fallback_generate_uses_phrase_keywords_only() -> None:
    draft = suggestion_service._fallback_generate(  # type: ignore[attr-defined]
        "tôi muốn chặn thông tin về Công ty X"
    )
    folded_any_of = {
        suggestion_service._fold_text(value)  # type: ignore[attr-defined]
        for value in _extract_first_context_keyword_any_of(draft)
    }
    assert "cong ty x" in folded_any_of
    assert "muon" not in folded_any_of
    assert "thong" not in folded_any_of
    assert "tin" not in folded_any_of


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
        if str(signal.get("field") or "").strip() != "context_keywords":
            continue
        raw_any_of = signal.get("any_of")
        if isinstance(raw_any_of, list):
            return [str(item) for item in raw_any_of]
    return []


def _extract_folded_context_terms(draft: object) -> set[str]:
    terms = getattr(draft, "context_terms", [])  # type: ignore[attr-defined]
    out: set[str] = set()
    for term in list(terms or []):
        text = str(getattr(term, "term", "") or "")
        folded = suggestion_service._fold_text(text)  # type: ignore[attr-defined]
        if folded:
            out.add(folded)
    return out


@pytest.mark.parametrize(
    ("prompt", "expected_phrase"),
    [
        ("tôi muốn chặn thông tin về Công ty X", "công ty x"),
        ("tôi muốn chặn thông tin về Cán bộ X", "cán bộ x"),
        ("tôi muốn chặn các nội dung nói xấu về Công ty X", "công ty x"),
    ],
)
def test_phase_a_generate_draft_sanitizes_noise_tokens_from_context_keywords(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    expected_phrase: str,
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
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return []

    def _fake_generate_with_llm(
        _prompt: str,
        *,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (prompt_keyword_bundle, policy_chunks, rule_references, literal_detection)
        payload = {
            "rule": {
                "stable_key": "personal.custom.phasea.sanitize",
                "name": "phase a sanitize",
                "description": "sanitize noisy tokens",
                "scope": "prompt",
                "conditions": {
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": [expected_phrase, "muon", "thong", "tin", "noi", "dung", "xau"],
                            }
                        }
                    ]
                },
                "action": "block",
                "severity": "high",
                "priority": 80,
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

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_service, "_generate_with_llm", _fake_generate_with_llm)

    draft, _meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt=prompt,
    )

    folded_any_of = {
        suggestion_service._fold_text(value)  # type: ignore[attr-defined]
        for value in _extract_first_context_keyword_any_of(draft)
    }
    assert suggestion_service._fold_text(expected_phrase) in folded_any_of  # type: ignore[attr-defined]
    assert "muon" not in folded_any_of
    assert "thong" not in folded_any_of
    assert "tin" not in folded_any_of
    assert "noi" not in folded_any_of
    assert "dung" not in folded_any_of
    assert "xau" not in folded_any_of


@pytest.mark.parametrize(
    ("prompt", "expected_phrase"),
    [
        ("toi muon chan thong tin ve giang vien y", "giang vien y"),
        (
            "toi muon chan thong tin ve nguoi phu trach tuyen dung ten l",
            "tuyen dung",
        ),
    ],
)
def test_phase_a_generate_draft_disables_internal_code_entity_fallback_for_non_literal_prompt(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    expected_phrase: str,
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
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return []

    def _fake_generate_with_llm(
        _prompt: str,
        *,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (prompt_keyword_bundle, policy_chunks, rule_references, literal_detection)
        payload = {
            "rule": {
                "stable_key": "personal.custom.phasea.internal_code_fallback",
                "name": "phase a internal code fallback",
                "description": "simulate bad llm fallback",
                "scope": "prompt",
                "conditions": {"any": [{"entity_type": "INTERNAL_CODE", "min_score": 0.8}]},
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

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_service, "_generate_with_llm", _fake_generate_with_llm)

    draft, _meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt=prompt,
    )

    assert suggestion_service._contains_entity_type(  # type: ignore[attr-defined]
        draft.rule.conditions, {"INTERNAL_CODE"}
    ) is False
    assert suggestion_service._has_context_keyword_signal(  # type: ignore[attr-defined]
        draft.rule.conditions
    )
    folded_any_of = {
        suggestion_service._fold_text(value)  # type: ignore[attr-defined]
        for value in _extract_first_context_keyword_any_of(draft)
    }
    assert folded_any_of
    assert suggestion_service._fold_text(expected_phrase) in folded_any_of  # type: ignore[attr-defined]


def test_phase_a_related_rule_references_are_style_only_and_domain_guarded() -> None:
    refs = suggestion_service._to_llm_style_rule_references(  # type: ignore[attr-defined]
        prompt="toi muon chan tai lieu noi bo chua cong bo cua Cong ty X",
        rule_references=[
            {
                "rule_id": "r-company",
                "stable_key": "personal.custom.company_x",
                "name": "Cong ty X internal policy",
                "description": "bao ve cong ty x tai lieu noi bo",
                "scope": "prompt",
                "action": "block",
                "severity": "high",
                "priority": 100,
                "match_mode": "strict_keyword",
                "origin": "personal_rule",
                "prompt_overlap_score": 0.91,
                "conditions": {
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["tang muc thu", "dieu chinh hoc phi"],
                            }
                        }
                    ]
                },
            },
            {
                "rule_id": "r-school",
                "stable_key": "personal.custom.school_x",
                "name": "Truong X hoc phi",
                "description": "dieu chinh hoc phi truong x",
                "scope": "prompt",
                "action": "block",
                "severity": "high",
                "priority": 90,
                "match_mode": "strict_keyword",
                "origin": "personal_rule",
                "prompt_overlap_score": 0.7,
            },
        ],
    )
    assert refs
    assert refs[0]["rule_id"] == "r-company"
    assert all("conditions" not in ref for ref in refs)
    assert all(str(ref.get("rule_id")) != "r-school" for ref in refs)


@pytest.mark.parametrize(
    ("prompt", "expected_keywords", "expected_context_terms", "forbidden_terms"),
    [
        (
            "toi muon chan tai lieu noi bo chua cong bo cua Cong ty X",
            {"cong ty x"},
            {"tai lieu noi bo", "chua cong bo"},
            {"tang muc thu", "dong cao hon", "dieu chinh hoc phi", "literal refine required"},
        ),
        (
            "toi muon chan cac noi dung ve ho so ky luat noi bo cua Cong ty N",
            {"cong ty n"},
            {"ho so ky luat", "noi bo"},
            {"tang muc thu", "dong cao hon", "dieu chinh hoc phi", "literal refine required"},
        ),
        (
            "toi muon chan thong tin ve Can bo X",
            {"can bo x"},
            set(),
            {"tang muc thu", "dong cao hon", "dieu chinh hoc phi", "literal refine required"},
        ),
        (
            "toi muon chan cac noi dung noi xau ve Cong ty X",
            {"cong ty x"},
            {"noi xau"},
            {"tang muc thu", "dong cao hon", "dieu chinh hoc phi", "literal refine required"},
        ),
    ],
)
def test_phase_a_generate_draft_drops_unrelated_prefill_context_terms(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    expected_keywords: set[str],
    expected_context_terms: set[str],
    forbidden_terms: set[str],
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
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return [
                {
                    "rule_id": "r-legacy",
                    "stable_key": "personal.custom.legacy",
                    "name": "Legacy suggestion",
                    "description": "dieu chinh hoc phi",
                    "scope": "prompt",
                    "action": "block",
                    "severity": "high",
                    "priority": 88,
                    "match_mode": "strict_keyword",
                    "origin": "personal_rule",
                    "prompt_overlap_score": 0.25,
                    "conditions": {
                        "all": [
                            {
                                "signal": {
                                    "field": "context_keywords",
                                    "any_of": ["tang muc thu", "dong cao hon", "dieu chinh hoc phi"],
                                }
                            }
                        ]
                    },
                }
            ]

    def _fake_generate_with_llm(
        _prompt: str,
        *,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (prompt_keyword_bundle, policy_chunks, rule_references, literal_detection)
        target_keywords = list(prompt_keyword_bundle.get("phrases") or [])
        payload = {
            "rule": {
                "stable_key": "personal.custom.phasea.prefill",
                "name": "phase a prefill",
                "description": "drop unrelated linked terms",
                "scope": "prompt",
                "conditions": {
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": [
                                    "literal refine required",
                                    *target_keywords,
                                    "noi xau",
                                    "tang muc thu",
                                    "dong cao hon",
                                    "dieu chinh hoc phi",
                                ],
                            }
                        }
                    ]
                },
                "action": "block",
                "severity": "high",
                "priority": 80,
                "match_mode": "strict_keyword",
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "tang muc thu",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                },
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "dong cao hon",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                },
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "dieu chinh hoc phi",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                },
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "literal refine required",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                },
            ],
        }
        draft = suggestion_service.RuleSuggestionDraftPayload.model_validate(payload)  # type: ignore[attr-defined]
        return draft, {
            "source": "llm",
            "provider": "mock",
            "model": "mock-model",
            "fallback_used": False,
        }

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_service, "_generate_with_llm", _fake_generate_with_llm)

    draft, _meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt=prompt,
    )

    folded_any_of = {
        suggestion_service._fold_text(value)  # type: ignore[attr-defined]
        for value in _extract_first_context_keyword_any_of(draft)
    }
    for expected in expected_keywords:
        assert expected in folded_any_of
    for forbidden in forbidden_terms:
        assert forbidden not in folded_any_of

    folded_context_terms = _extract_folded_context_terms(draft)
    for expected in expected_context_terms:
        assert expected in folded_context_terms
    for forbidden in forbidden_terms:
        assert forbidden not in folded_context_terms


def test_phase_a_normalize_draft_forces_simple_builder_compatible_conditions() -> None:
    payload = suggestion_service.RuleSuggestionDraftPayload.model_validate(  # type: ignore[attr-defined]
        {
            "rule": {
                "stable_key": "personal.custom.builder.normalize",
                "name": "builder normalize",
                "description": "normalize nested unsupported conditions",
                "scope": "chat",
                "conditions": {
                    "any": [
                        {"signal": {"field": "context_keywords", "contains": "ho so ky luat"}},
                        {
                            "all": [
                                {"entity_type": "EMAIL", "min_score": 0.7},
                                {"signal": {"field": "risk_boost", "gte": 0.3}},
                            ]
                        },
                        {"not": {"entity_type": "PHONE"}},
                    ]
                },
                "action": "block",
                "severity": "high",
                "priority": 100,
                "match_mode": "strict_keyword",
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "ho so ky luat",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                }
            ],
        }
    )

    normalized = suggestion_service._normalize_draft(payload)  # type: ignore[attr-defined]
    assert suggestion_service._is_simple_builder_compatible_conditions(  # type: ignore[attr-defined]
        normalized.rule.conditions
    )
    rows = normalized.rule.conditions["all"]
    assert isinstance(rows, list) and rows
    entity_rows = [row for row in rows if isinstance(row, dict) and isinstance(row.get("entity_type"), str)]
    assert any(str(row.get("entity_type")).upper() == "EMAIL" for row in entity_rows)
    assert all(str(row.get("entity_type")).upper() != "PHONE" for row in entity_rows)
    assert any(
        isinstance(row, dict)
        and isinstance(row.get("signal"), dict)
        and str((row.get("signal") or {}).get("field")) == "context_keywords"
        for row in rows
    )


@pytest.mark.parametrize(
    ("prompt", "expected_keywords", "expected_context_terms", "forbidden_keywords", "forbidden_context_terms"),
    [
        (
            "toi muon chan thong tin ve tro giang k",
            {"tro giang k"},
            set(),
            {"noi bo", "chua cong bo"},
            {"internal_code"},
        ),
        (
            "toi muon chan cac noi dung ve bien ban hop chien luoc noi bo cua tap doan m",
            {"tap doan m"},
            {"bien ban hop chien luoc", "noi bo"},
            {"noi bo", "chua cong bo"},
            {"tap doan m", "bien ban hop chien luoc noi bo"},
        ),
        (
            "toi muon chan cac noi dung ve danh sach thuong quy chua cong bo cua bo phan p",
            {"bo phan p"},
            {"danh sach thuong quy", "chua cong bo"},
            {"noi bo", "chua cong bo"},
            {"bo phan p", "danh sach thuong quy chua cong bo"},
        ),
        (
            "toi muon chan cac noi dung boi nho ve co van r",
            {"co van r"},
            {"boi nho"},
            {"co van", "boi nho ve co van r"},
            {"co van", "boi nho ve co van r", "co van r"},
        ),
        (
            "toi muon chan cac noi dung hoi ve ngan sach van hanh noi bo cua du an v",
            {"du an v"},
            {"ngan sach van hanh", "noi bo"},
            {"noi bo", "chua cong bo"},
            {"du an v", "ngan sach van hanh noi bo"},
        ),
    ],
)
def test_phase_a_semantic_generation_preserves_entity_business_phrase_and_role_split(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    expected_keywords: set[str],
    expected_context_terms: set[str],
    forbidden_keywords: set[str],
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
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return []

    def _fake_generate_with_llm(
        _prompt: str,
        *,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (prompt_keyword_bundle, policy_chunks, rule_references, literal_detection)
        payload = {
            "rule": {
                "stable_key": "personal.custom.phasea.semantic.noisy",
                "name": "phase a semantic noisy",
                "description": "simulate semantic drift + duplication",
                "scope": "chat",
                "conditions": {
                    "any": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": [
                                    "noi bo",
                                    "chua cong bo",
                                    "co van",
                                    "boi nho ve co van r",
                                    "literal refine required",
                                ],
                            }
                        },
                        {"not": {"entity_type": "INTERNAL_CODE", "min_score": 0.8}},
                    ]
                },
                "action": "block",
                "severity": "high",
                "priority": 100,
                "match_mode": "strict_keyword",
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "noi bo",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                },
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "chua cong bo",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                },
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "boi nho ve co van r",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                },
            ],
        }
        draft = suggestion_service.RuleSuggestionDraftPayload.model_validate(payload)  # type: ignore[attr-defined]
        return draft, {
            "source": "llm",
            "provider": "mock",
            "model": "mock-model",
            "fallback_used": False,
        }

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_service, "_generate_with_llm", _fake_generate_with_llm)

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
    assert folded_keywords == expected_keywords
    assert len(folded_keywords) <= 2
    for forbidden in forbidden_keywords:
        assert forbidden not in folded_keywords

    folded_context_terms = _extract_folded_context_terms(draft)
    assert expected_context_terms.issubset(folded_context_terms)
    assert folded_keywords.isdisjoint(folded_context_terms)
    for forbidden in forbidden_context_terms:
        assert forbidden not in folded_context_terms

    assert suggestion_service._contains_entity_type(  # type: ignore[attr-defined]
        draft.rule.conditions, {"INTERNAL_CODE"}
    ) is False
    assert suggestion_service._is_simple_builder_compatible_conditions(  # type: ignore[attr-defined]
        draft.rule.conditions
    )


@pytest.mark.parametrize(
    ("prompt", "expected_keyword"),
    [
        (
            "toi muon chan cac noi dung noi xau ve quan ly b",
            "quan ly b",
        ),
        (
            "toi muon chan cac noi dung hoi ve quy trinh xu ly su co noi bo cua du an c",
            "du an c",
        ),
    ],
)
def test_phase_a_target_entity_phrase_is_mandatory_keyword_when_present(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    expected_keyword: str,
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
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return []

    def _fake_generate_with_llm(
        _prompt: str,
        *,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (prompt_keyword_bundle, policy_chunks, rule_references, literal_detection)
        payload = {
            "rule": {
                "stable_key": "personal.custom.phasea.target.entity",
                "name": "phase a target entity",
                "description": "simulate generic keyword drift",
                "scope": "chat",
                "conditions": {
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["noi xau", "noi bo", "chua cong bo"],
                            }
                        }
                    ]
                },
                "action": "block",
                "severity": "high",
                "priority": 100,
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
                },
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "noi bo",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                },
            ],
        }
        draft = suggestion_service.RuleSuggestionDraftPayload.model_validate(payload)  # type: ignore[attr-defined]
        return draft, {
            "source": "llm",
            "provider": "mock",
            "model": "mock-model",
            "fallback_used": False,
        }

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_service, "_generate_with_llm", _fake_generate_with_llm)

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
    assert expected_keyword in folded_keywords
    assert folded_keywords != {"noi xau"}
    assert folded_keywords != {"noi bo"}
    assert folded_keywords != {"chua cong bo"}
    assert suggestion_service._contains_entity_type(  # type: ignore[attr-defined]
        draft.rule.conditions, {"INTERNAL_CODE"}
    ) is False


@pytest.mark.parametrize(
    ("prompt", "expected_keyword", "expected_context_terms"),
    [
        (
            "toi muon chan cac noi dung ve ke hoach mo rong thi truong noi bo cua cong ty z",
            "cong ty z",
            {"ke hoach mo rong thi truong", "noi bo"},
        ),
        (
            "toi muon chan cac noi dung lien quan den bao cao loi nhuan quy chua cong bo cua tap doan a",
            "tap doan a",
            {"bao cao loi nhuan quy", "chua cong bo"},
        ),
        (
            "toi muon chan cac noi dung ve thong tin mat noi bo cua bo phan d",
            "bo phan d",
            {"thong tin mat", "noi bo"},
        ),
    ],
)
def test_phase_a_linked_context_terms_keep_full_business_phrase(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    expected_keyword: str,
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
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return []

    def _fake_generate_with_llm(
        _prompt: str,
        *,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (prompt_keyword_bundle, policy_chunks, rule_references, literal_detection)
        payload = {
            "rule": {
                "stable_key": "personal.custom.phasea.full_phrase",
                "name": "phase a full phrase",
                "description": "simulate truncated business phrase",
                "scope": "chat",
                "conditions": {
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["noi bo", "chua cong bo"],
                            }
                        }
                    ]
                },
                "action": "block",
                "severity": "high",
                "priority": 100,
                "match_mode": "strict_keyword",
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "noi bo",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                },
                {
                    "entity_type": "CUSTOM_SECRET",
                    "term": "chua cong bo",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                },
            ],
        }
        draft = suggestion_service.RuleSuggestionDraftPayload.model_validate(payload)  # type: ignore[attr-defined]
        return draft, {
            "source": "llm",
            "provider": "mock",
            "model": "mock-model",
            "fallback_used": False,
        }

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_service, "_generate_with_llm", _fake_generate_with_llm)

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
    assert expected_keyword in folded_keywords

    folded_context_terms = _extract_folded_context_terms(draft)
    assert expected_context_terms.issubset(folded_context_terms)
    assert folded_keywords.isdisjoint(folded_context_terms)


@pytest.mark.parametrize(
    ("prompt", "expected_keyword", "expected_context_terms"),
    [
        (
            "toi muon chan cac noi dung hoi ve quy trinh xu ly su co noi bo cua du an c",
            "du an c",
            {"quy trinh xu ly su co", "noi bo"},
        ),
        (
            "toi muon chan cac noi dung ve thong tin mat noi bo cua bo phan d",
            "bo phan d",
            {"thong tin mat", "noi bo"},
        ),
    ],
)
def test_phase_a_generation_failure_falls_back_to_minimal_safe_draft(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    expected_keyword: str,
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
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return []

    def _raise_llm_error(
        _prompt: str,
        *,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (prompt_keyword_bundle, policy_chunks, rule_references, literal_detection)
        raise RuntimeError("llm unavailable")

    def _raise_fallback_error(_prompt: str) -> object:
        raise RuntimeError("fallback unavailable")

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_service, "_generate_with_llm", _raise_llm_error)
    monkeypatch.setattr(suggestion_service, "_fallback_generate", _raise_fallback_error)

    draft, meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt=prompt,
    )

    assert str(meta.get("source")) == "safe_minimal_fallback_after_generation_error"
    folded_keywords = {
        suggestion_service._fold_text(value)  # type: ignore[attr-defined]
        for value in _extract_first_context_keyword_any_of(draft)
    }
    assert expected_keyword in folded_keywords

    folded_context_terms = _extract_folded_context_terms(draft)
    assert expected_context_terms.issubset(folded_context_terms)
    assert suggestion_service._contains_entity_type(  # type: ignore[attr-defined]
        draft.rule.conditions, {"INTERNAL_CODE"}
    ) is False
    assert suggestion_service._is_simple_builder_compatible_conditions(  # type: ignore[attr-defined]
        draft.rule.conditions
    )


def test_phase_a_debug_placeholder_text_does_not_leak_from_literal_refine_fallback(
    monkeypatch: pytest.MonkeyPatch,
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
        ) -> list[dict[str, object]]:
            _ = (user_id, top_k)
            return []

    def _raise_llm_error(
        _prompt: str,
        *,
        prompt_keyword_bundle: dict[str, list[str]],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
        literal_detection: LiteralDetectionResult,
    ) -> tuple[object, dict[str, object]]:
        _ = (prompt_keyword_bundle, policy_chunks, rule_references, literal_detection)
        raise RuntimeError("llm unavailable")

    def _literal_refine_fallback(_prompt: str) -> object:
        return suggestion_service._build_literal_refinement_draft(  # type: ignore[attr-defined]
            prompt=_prompt,
            action=RuleAction.block,
            stable_suffix="unit-test",
        )

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_service, "_generate_with_llm", _raise_llm_error)
    monkeypatch.setattr(suggestion_service, "_fallback_generate", _literal_refine_fallback)

    draft, _meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt="toi muon chan cac noi dung hoi ve quy trinh xu ly su co noi bo cua du an c",
    )

    folded_name = suggestion_service._fold_text(str(draft.rule.name or ""))  # type: ignore[attr-defined]
    folded_desc = suggestion_service._fold_text(str(draft.rule.description or ""))  # type: ignore[attr-defined]
    assert "prompt keyword refinement" not in folded_name
    assert "cannot generate from this prompt yet" not in folded_name
    assert "literal refine required" not in folded_name
    assert "cannot generate from this prompt yet" not in folded_desc
    assert all(
        suggestion_service._fold_text(str(term.term or "")) != "literal refine required"  # type: ignore[attr-defined]
        for term in draft.context_terms
    )
