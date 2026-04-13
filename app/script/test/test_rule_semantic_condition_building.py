from __future__ import annotations

from app.common.enums import MatchMode
from app.rule import service as rule_service
from app.rule.schemas import RuleContextTermIn


def _context_keyword_terms(conditions: dict[str, object]) -> set[str]:
    return rule_service._extract_context_keyword_terms_from_conditions(conditions)


def test_build_semantic_conditions_adds_strong_topic_term_for_manual_rule() -> None:
    conditions = {
        "all": [
            {
                "signal": {
                    "field": "context_keywords",
                    "any_of": ["truong nhom q"],
                }
            }
        ]
    }

    built = rule_service._build_semantic_conditions(
        conditions=conditions,
        match_mode=MatchMode.keyword_plus_semantic,
        context_terms=[
            RuleContextTermIn(entity_type="SEM_TOPIC", term="noi xau"),
        ],
    )

    assert _context_keyword_terms(built) == {"truong nhom q", "noi xau"}


def test_build_semantic_conditions_prefers_specific_business_phrase_over_weak_modifier() -> None:
    conditions = {
        "all": [
            {
                "signal": {
                    "field": "context_keywords",
                    "any_of": ["trung tam m"],
                }
            }
        ]
    }

    built = rule_service._build_semantic_conditions(
        conditions=conditions,
        match_mode=MatchMode.keyword_plus_semantic,
        context_terms=[
            RuleContextTermIn(entity_type="SEM_TOPIC", term="tai lieu"),
            RuleContextTermIn(entity_type="SEM_TOPIC", term="noi bo"),
        ],
    )

    assert _context_keyword_terms(built) == {"trung tam m", "tai lieu noi bo"}


def test_build_auto_context_terms_from_and_conditions_materializes_target_and_topic() -> None:
    conditions = {
        "all": [
            {
                "signal": {
                    "field": "context_keywords",
                    "any_of": ["truong nhom q"],
                }
            },
            {
                "signal": {
                    "field": "context_keywords",
                    "any_of": ["noi xau"],
                }
            },
        ]
    }

    built = rule_service._build_auto_context_terms_from_conditions(conditions=conditions)
    built_terms = {str(row.term or "").strip().lower() for row in built}
    assert built_terms == {"truong nhom q", "noi xau"}


def test_build_semantic_conditions_replaces_stale_topic_nodes_on_rebuild() -> None:
    conditions = {
        "all": [
            {
                "signal": {
                    "field": "context_keywords",
                    "any_of": ["truong nhom q"],
                }
            },
            {
                "signal": {
                    "field": "context_keywords",
                    "any_of": ["noi xau"],
                }
            },
        ]
    }

    built = rule_service._build_semantic_conditions(
        conditions=conditions,
        match_mode=MatchMode.keyword_plus_semantic,
        context_terms=[
            RuleContextTermIn(entity_type="SEM_TOPIC", term="boi nho"),
        ],
    )

    assert _context_keyword_terms(built) == {"truong nhom q", "boi nho"}
