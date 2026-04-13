from app.common.enums import MatchMode, RagMode, RuleAction, RuleScope, RuleSeverity
from app.suggestion.schemas import (
    RuleSuggestionDraftContextTerm,
    RuleSuggestionDraftPayload,
    RuleSuggestionDraftRule,
)
from app.suggestion.suggestion_postprocess import _normalize_draft


def _build_payload(*, context_terms: list[RuleSuggestionDraftContextTerm]) -> RuleSuggestionDraftPayload:
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
            match_mode=MatchMode.strict_keyword,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=context_terms,
    )


def test_normalize_draft_sets_strict_keyword_when_context_terms_empty():
    payload = _build_payload(context_terms=[])

    normalized = _normalize_draft(payload)

    assert normalized.rule.match_mode == MatchMode.strict_keyword


def test_normalize_draft_sets_keyword_plus_semantic_when_context_terms_exist():
    payload = _build_payload(
        context_terms=[
            RuleSuggestionDraftContextTerm(
                entity_type="CONTEXT_KEYWORD",
                term="noi xau",
                lang="vi",
                weight=1.0,
                window_1=60,
                window_2=20,
                enabled=True,
            )
        ]
    )

    normalized = _normalize_draft(payload)

    assert normalized.rule.match_mode == MatchMode.keyword_plus_semantic
