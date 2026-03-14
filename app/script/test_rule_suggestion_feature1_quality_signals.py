from __future__ import annotations

from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity
from app.suggestion import service as suggestion_service
from app.suggestion.schemas import (
    RuleSuggestionDraftContextTerm,
    RuleSuggestionDraftPayload,
    RuleSuggestionDraftRule,
)


def _sample_draft() -> RuleSuggestionDraftPayload:
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key="company.custom.test.feature1",
            name="Feature1 quality test",
            description="validate explanation and quality signals",
            scope=RuleScope.prompt,
            conditions={"any": [{"entity_type": "PHONE"}]},
            action=RuleAction.block,
            severity=RuleSeverity.high,
            priority=100,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[
            RuleSuggestionDraftContextTerm(
                entity_type="PHONE",
                term="hotline",
                lang="vi",
                weight=1.0,
                window_1=60,
                window_2=20,
                enabled=True,
            )
        ],
    )


def _abstract_context_draft() -> RuleSuggestionDraftPayload:
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key="company.custom.test.abstract",
            name="Abstract context keyword rule",
            description="runtime-usability guard test",
            scope=RuleScope.prompt,
            conditions={
                "all": [
                    {
                        "signal": {
                            "field": "context_keywords",
                            "any_of": ["exact", "token"],
                        }
                    }
                ]
            },
            action=RuleAction.mask,
            severity=RuleSeverity.medium,
            priority=100,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[],
    )


def test_feature1_explanation_and_quality_signals_shape() -> None:
    draft = _sample_draft()
    prompt = "Tao rule block so dien thoai va hotline noi bo"
    duplicate_meta = {
        "decision": "DIFFERENT",
        "confidence": 0.92,
    }
    generation_meta = {
        "source": "llm",
    }

    explanation = suggestion_service._build_suggestion_explanation(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=draft,
        duplicate_meta=duplicate_meta,
    )
    quality = suggestion_service._build_quality_signals(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=draft,
        duplicate_meta=duplicate_meta,
        generation_meta=generation_meta,
    )

    assert isinstance(explanation.summary, str) and explanation.summary.strip()
    assert (
        isinstance(explanation.detected_intent, str)
        and explanation.detected_intent.strip()
    )
    assert isinstance(explanation.derived_terms, list)
    assert isinstance(explanation.action_reason, str) and explanation.action_reason.strip()

    assert 0.0 <= float(quality.intent_confidence) <= 1.0
    assert quality.duplicate_risk in {"low", "medium", "high"}
    assert quality.conflict_risk == "unknown"
    assert quality.generation_source == "llm"
    assert quality.has_policy_context is False
    assert isinstance(quality.runtime_usable, bool)
    assert isinstance(quality.runtime_warnings, list)


def test_feature1_generation_source_is_heuristic_fallback_when_fallback_used() -> None:
    draft = _sample_draft()
    duplicate_meta = {
        "decision": "DIFFERENT",
        "confidence": 0.8,
    }

    quality = suggestion_service._build_quality_signals(  # type: ignore[attr-defined]
        prompt="Tao rule mask thong tin nhay cam",
        draft=draft,
        duplicate_meta=duplicate_meta,
        generation_meta={"source": "fallback_generator_after_normalize_error"},
    )

    assert quality.generation_source == "heuristic_fallback"


def test_runtime_usability_penalizes_abstract_context_keywords() -> None:
    draft = _abstract_context_draft()
    duplicate_meta = {
        "decision": "DIFFERENT",
        "confidence": 0.92,
    }
    generation_meta = {
        "source": "llm",
    }

    quality = suggestion_service._build_quality_signals(  # type: ignore[attr-defined]
        prompt="Tao rule mask token noi bo",
        draft=draft,
        duplicate_meta=duplicate_meta,
        generation_meta=generation_meta,
    )
    quality_baseline = suggestion_service._build_quality_signals(  # type: ignore[attr-defined]
        prompt="Tao rule block so dien thoai va hotline noi bo",
        draft=_sample_draft(),
        duplicate_meta=duplicate_meta,
        generation_meta=generation_meta,
    )

    assert quality.runtime_usable is False
    assert "abstract_context_keywords_not_runtime_usable" in quality.runtime_warnings
    assert quality.intent_confidence < quality_baseline.intent_confidence


def test_runtime_usability_auto_repair_for_exact_secret_prompt() -> None:
    draft = _abstract_context_draft()
    repaired, runtime_meta = suggestion_service._apply_runtime_usability_constraint(  # type: ignore[attr-defined]
        prompt="Che token noi bo ZXQ-UNSEEN-9981",
        draft=draft,
    )

    assert runtime_meta.get("repair_applied") is True
    assert runtime_meta.get("runtime_usable") is True
    assert not runtime_meta.get("warnings")
    assert suggestion_service._condition_has_context_keyword_term(  # type: ignore[attr-defined]
        repaired.rule.conditions,
        "zxq-unseen-9981",
    )
