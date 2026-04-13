from __future__ import annotations

import json
import inspect
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.common.enums import MatchMode, RagMode, RuleAction, RuleScope, RuleSeverity
from app.suggestion import service as suggestion_service
from app.suggestion.literal_detector import LiteralDetectionResult
from app.suggestion.schemas import (
    RuleSuggestionDraftContextTerm,
    RuleSuggestionDraftPayload,
    RuleSuggestionDraftRule,
)


def _sample_draft(
    *,
    stable_key: str = "personal.custom.phaseb1",
    match_mode: MatchMode = MatchMode.strict_keyword,
) -> RuleSuggestionDraftPayload:
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key=stable_key,
            name="Phase B1 draft",
            description="contract alignment sample",
            scope=RuleScope.prompt,
            conditions={"all": [{"signal": {"field": "context_keywords", "any_of": ["cán bộ x"]}}]},
            action=RuleAction.mask,
            severity=RuleSeverity.medium,
            priority=55,
            match_mode=match_mode,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[
            RuleSuggestionDraftContextTerm(
                entity_type="INTERNAL_CODE",
                term="cán bộ x",
                lang="vi",
                weight=1.0,
                window_1=60,
                window_2=20,
                enabled=True,
            )
        ],
    )


def test_phase_b1_suggestion_rule_contract_exposes_create_rule_fields() -> None:
    rule = RuleSuggestionDraftRule(
        stable_key="personal.custom.phaseb1.contract",
        name="Contract shape",
        description="shape alignment",
        conditions={"any": [{"entity_type": "EMAIL"}]},
    )
    dumped = rule.model_dump(mode="json")
    assert dumped["match_mode"] == "strict_keyword"
    assert dumped["scope"] == "prompt"
    assert dumped["action"] == "mask"
    assert dumped["severity"] == "medium"
    assert "conditions" in dumped


def test_phase_b1_normalize_and_dedupe_include_match_mode() -> None:
    draft = _sample_draft(match_mode=MatchMode.keyword_plus_semantic)
    normalized = suggestion_service._normalize_draft(draft)  # type: ignore[attr-defined]
    canonical = suggestion_service._canonical_rule_for_dedupe(  # type: ignore[attr-defined]
        normalized.rule
    )
    assert normalized.rule.match_mode == MatchMode.keyword_plus_semantic
    assert canonical["match_mode"] == "keyword_plus_semantic"


class _FakeExecResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)


class _FakeListSession:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def exec(self, _statement: object) -> _FakeExecResult:
        return _FakeExecResult(self._rows)


def test_phase_b1_rule_references_include_match_mode() -> None:
    row = SimpleNamespace(
        id=uuid4(),
        company_id=uuid4(),
        stable_key="personal.custom.can_bo_x",
        name="Can bo X sensitive",
        description="cán bộ x hồ sơ",
        scope=RuleScope.prompt,
        action=RuleAction.block,
        severity=RuleSeverity.high,
        priority=80,
        match_mode=MatchMode.keyword_plus_semantic,
        rag_mode=RagMode.off,
        conditions={
            "all": [{"signal": {"field": "context_keywords", "any_of": ["cán bộ x"]}}]
        },
    )
    refs = suggestion_service._build_rule_references(  # type: ignore[attr-defined]
        session=_FakeListSession([row]),
        company_id=row.company_id,
        prompt="tôi muốn chặn thông tin về Cán bộ X",
        limit=1,
    )
    assert refs
    assert refs[0]["match_mode"] == "keyword_plus_semantic"


def test_phase_b1_generate_with_llm_schema_mentions_match_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def _fake_generate_text_sync(
        *,
        prompt: str,
        system_prompt: str,
        provider: str,
    ) -> object:
        _ = provider
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        payload = {
            "rule": {
                "stable_key": "personal.custom.phaseb1.llm",
                "name": "LLM phase B1",
                "description": "llm contract",
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
                "match_mode": "keyword_plus_semantic",
                "rag_mode": "off",
                "enabled": True,
            },
            "context_terms": [],
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

    draft, _meta = suggestion_service._generate_with_llm(  # type: ignore[attr-defined]
        "tôi muốn chặn thông tin về Cán bộ X",
        prompt_keyword_bundle={
            "phrases": ["cán bộ x"],
            "tokens": ["thông", "tin"],
        },
        policy_chunks=[],
        rule_references=[],
        literal_detection=literal_detection,
    )

    assert draft.rule.match_mode == MatchMode.keyword_plus_semantic
    assert '"match_mode": "strict_keyword|keyword_plus_semantic"' in captured["system_prompt"]


def test_phase_b1_apply_path_sets_rule_match_mode_explicitly() -> None:
    source = inspect.getsource(suggestion_service._apply_rule_draft)  # type: ignore[attr-defined]
    assert "match_mode=rule_draft.match_mode" in source
