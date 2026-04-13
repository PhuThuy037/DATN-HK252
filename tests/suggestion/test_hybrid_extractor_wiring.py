from __future__ import annotations

from types import SimpleNamespace

from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity
from app.suggestion.schemas import RuleSuggestionDraftPayload, RuleSuggestionDraftRule
from app.suggestion.suggestion_extractor import HybridExtractionResult
from app.suggestion import suggestion_extractor
from app.suggestion import suggestion_generation


def _minimal_draft() -> RuleSuggestionDraftPayload:
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key="personal.custom.suggested.test",
            name="Suggested prompt policy",
            description="test",
            scope=RuleScope.prompt,
            conditions={
                "all": [
                    {"signal": {"field": "context_keywords", "any_of": ["context"]}},
                ]
            },
            action=RuleAction.block,
            severity=RuleSeverity.high,
            priority=90,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[],
    )


class _FakeLiteralDetection:
    known_pii_type = None
    candidate_tokens: list[str] = []
    decision_hint = ""
    intent_literal = False
    top_token = None

    def to_dict(self) -> dict[str, object]:
        return {}


class _FakeService:
    @staticmethod
    def _normalize_non_empty(*, value: str | None, field: str) -> str:
        assert field == "prompt"
        return str(value or "").strip()

    @staticmethod
    def _literal_detection(prompt: str, *, limit: int = 8) -> _FakeLiteralDetection:
        _ = prompt, limit
        return _FakeLiteralDetection()

    @staticmethod
    def _to_str_list(value):
        return [str(item) for item in list(value or []) if item]

    @staticmethod
    def _sanitize_debug_placeholder_text(*, prompt: str, draft: RuleSuggestionDraftPayload):
        _ = prompt
        return draft

    @staticmethod
    def _realign_literal_specific_draft(*, prompt: str, draft: RuleSuggestionDraftPayload):
        _ = prompt
        return draft

    @staticmethod
    def _align_draft_with_prompt(prompt: str, draft: RuleSuggestionDraftPayload):
        _ = prompt
        return draft

    @staticmethod
    def _enforce_prompt_semantic_guard(prompt: str, draft: RuleSuggestionDraftPayload):
        _ = prompt
        return draft

    @staticmethod
    def _post_generate_intent_guard(*, prompt: str, draft: RuleSuggestionDraftPayload):
        _ = prompt
        return draft, {}

    @staticmethod
    def _apply_runtime_usability_constraint(*, prompt: str, draft: RuleSuggestionDraftPayload):
        _ = prompt
        return draft, {}

    @staticmethod
    def _sanitize_draft_context_keywords(
        *, draft: RuleSuggestionDraftPayload, prompt_keyword_bundle
    ):
        _ = prompt_keyword_bundle
        return draft

    @staticmethod
    def _filter_and_ground_context_terms(
        *, prompt: str, draft: RuleSuggestionDraftPayload, prompt_keyword_bundle
    ):
        _ = prompt, prompt_keyword_bundle
        return draft

    @staticmethod
    def _enforce_keyword_context_role_contract(
        *, prompt: str, draft: RuleSuggestionDraftPayload, prompt_keyword_bundle
    ):
        _ = prompt, prompt_keyword_bundle
        return draft, {}

    @staticmethod
    def _normalize_draft(draft: RuleSuggestionDraftPayload):
        return draft

    @staticmethod
    def _prompt_keywords(prompt: str, *, limit: int = 6):
        _ = limit
        prompt = str(prompt or "").lower()
        if "phòng k" in prompt or "phong k" in prompt:
            return {"phrases": ["phong k"], "tokens": ["phong", "k"]}
        return {"phrases": ["context"], "tokens": ["helper"]}

    @staticmethod
    def _extract_target_phrases(prompt: str, *, limit: int = 4):
        _ = limit
        prompt = str(prompt or "").lower()
        if "phòng k" in prompt or "phong k" in prompt:
            return ["phong k"]
        return []

    @staticmethod
    def _extract_business_noun_phrases(prompt: str, *, limit: int = 4):
        _ = limit
        prompt = str(prompt or "").lower()
        if "kế hoạch mở rộng thị trường" in prompt or "ke hoach mo rong thi truong" in prompt:
            return ["ke hoach mo rong thi truong"]
        return []

    @staticmethod
    def _extract_prompt_context_phrases(prompt: str, *, limit: int = 4):
        _ = limit
        prompt = str(prompt or "").lower()
        if "nội bộ" in prompt or "noi bo" in prompt:
            return ["noi bo"]
        return []

    @staticmethod
    def _extract_target_families(prompt: str):
        prompt = str(prompt or "").lower()
        if "phòng k" in prompt or "phong k" in prompt:
            return {"org_target"}
        return set()

    @staticmethod
    def _unique_phrase_values(values: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = str(value or "").strip().lower()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            out.append(cleaned)
        return out

    @staticmethod
    def _remove_redundant_subphrases(phrases: list[str], *, protected: set[str] | None = None):
        _ = protected
        return _FakeService._unique_phrase_values(phrases)

    @staticmethod
    def _is_generic_modifier_phrase(value: str) -> bool:
        return str(value or "").strip().lower() in {"noi bo", "chua cong bo"}

    @staticmethod
    def _fold_text(value: str) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _normalize_phrase_text(value: str) -> str:
        return str(value or "").strip().lower()


class _FakeRetriever:
    def __init__(self, *args, **kwargs):
        _ = args, kwargs
        self.captured_extraction = None

    def retrieve_policy_chunks(self, prompt: str, user_id, top_k: int = 3):
        _ = prompt, user_id, top_k
        return []

    def retrieve_related_rules(self, prompt: str, user_id, top_k: int = 3, extraction=None):
        _ = prompt, user_id, top_k
        self.captured_extraction = extraction
        return []


def test_extract_hybrid_rule_only_mode(monkeypatch):
    monkeypatch.setattr(suggestion_extractor, "USE_SPACY_EXTRACTOR", False)

    def _unexpected(prompt: str):
        raise AssertionError(f"spaCy path should not be called for {prompt!r}")

    monkeypatch.setattr(suggestion_extractor, "extract_with_spacy", _unexpected)
    result = suggestion_extractor.extract_hybrid("tôi muốn chặn thông tin về Công ty X")
    assert result.target_entities == ["cong ty x"]


def test_extract_hybrid_uses_spacy_merge_when_enabled(monkeypatch):
    monkeypatch.setattr(suggestion_extractor, "USE_SPACY_EXTRACTOR", True)
    monkeypatch.setattr(suggestion_extractor, "_extract_business_noun_phrases", lambda prompt, limit=4: [])
    monkeypatch.setattr(suggestion_extractor, "_extract_prompt_context_phrases", lambda prompt, limit=4: [])
    monkeypatch.setattr(
        suggestion_extractor,
        "_prompt_keywords",
        lambda prompt, limit=6: {"phrases": [], "tokens": []},
    )
    monkeypatch.setattr(
        suggestion_extractor,
        "extract_with_spacy",
        lambda prompt: HybridExtractionResult(
            target_entities=["phong k"],
            business_phrases=["tai lieu noi bo"],
            context_modifiers=["noi bo"],
            helper_tokens=[],
        ),
    )

    result = suggestion_extractor.extract_hybrid("tôi muốn chặn thông tin về Phòng K")
    assert result.target_entities == ["phong k"]
    assert "tai lieu noi bo" in result.business_phrases
    assert "noi bo" in result.context_modifiers


def test_generate_path_calls_extract_hybrid(monkeypatch):
    captured = {}
    monkeypatch.setattr(suggestion_generation, "_svc", lambda: _FakeService())
    monkeypatch.setattr(suggestion_generation, "SuggestionContextRetriever", _FakeRetriever)

    def _fake_extract_hybrid(prompt: str) -> HybridExtractionResult:
        captured["prompt"] = prompt
        return HybridExtractionResult(
            target_entities=["phong k"],
            business_phrases=["tai lieu noi bo"],
            context_modifiers=["noi bo"],
            helper_tokens=["helper-token"],
        )

    def _fake_generate_with_llm(
        prompt: str,
        *,
        extraction,
        prompt_keyword_bundle,
        policy_chunks,
        rule_references,
        literal_detection,
    ):
        captured["llm_prompt"] = prompt
        captured["extraction"] = extraction
        captured["bundle"] = prompt_keyword_bundle
        _ = policy_chunks, rule_references, literal_detection
        return _minimal_draft(), {"source": "llm"}

    monkeypatch.setattr(suggestion_generation, "extract_hybrid", _fake_extract_hybrid)
    monkeypatch.setattr(suggestion_generation, "_generate_with_llm", _fake_generate_with_llm)

    draft, meta = suggestion_generation._generate_draft_from_prompt(
        session=None,
        company_id=None,
        actor_user_id=None,
        prompt="tôi muốn chặn thông tin về Phòng K",
    )

    assert draft.rule.name == "Suggested prompt policy"
    assert meta["source"] == "llm"
    assert captured["prompt"] == "tôi muốn chặn thông tin về Phòng K"
    assert captured["bundle"]["phrases"] == ["phong k"]
    assert captured["bundle"]["tokens"] == ["helper-token"]
    assert captured["extraction"].target_entities == ["phong k"]


def test_generate_path_survives_hybrid_extraction_failure(monkeypatch):
    monkeypatch.setattr(suggestion_generation, "_svc", lambda: _FakeService())
    monkeypatch.setattr(suggestion_generation, "SuggestionContextRetriever", _FakeRetriever)

    def _raise_extract(prompt: str) -> HybridExtractionResult:
        raise RuntimeError(f"boom: {prompt}")

    def _fake_generate_with_llm(
        prompt: str,
        *,
        extraction,
        prompt_keyword_bundle,
        policy_chunks,
        rule_references,
        literal_detection,
    ):
        _ = prompt, policy_chunks, rule_references, literal_detection
        assert extraction.target_entities == []
        assert prompt_keyword_bundle["phrases"] == ["phong k"]
        return _minimal_draft(), {"source": "llm"}

    monkeypatch.setattr(suggestion_generation, "extract_hybrid", _raise_extract)
    monkeypatch.setattr(suggestion_generation, "_generate_with_llm", _fake_generate_with_llm)

    draft, meta = suggestion_generation._generate_draft_from_prompt(
        session=None,
        company_id=None,
        actor_user_id=None,
        prompt="tôi muốn chặn thông tin về Phòng K",
    )

    assert draft.rule.conditions["all"][0]["signal"]["any_of"] == ["context"]
    assert meta["source"] == "llm"
