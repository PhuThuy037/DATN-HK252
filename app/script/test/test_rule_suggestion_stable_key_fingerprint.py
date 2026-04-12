from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlmodel import select

from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity
# Load model modules for SQLAlchemy relationship registry side-effects used by Rule().
import app.auth.model as _auth_model  # noqa: F401
import app.company.model as _company_model  # noqa: F401
import app.company_member.model as _company_member_model  # noqa: F401
import app.conversation.model as _conversation_model  # noqa: F401
import app.messages.model as _messages_model  # noqa: F401
import app.prompt_entitity.model as _prompt_entity_model  # noqa: F401
import app.rule_change_log.model as _rule_change_log_model  # noqa: F401
from app.rule.model import Rule
import app.rule_embedding.model as _rule_embedding_model  # noqa: F401
from app.suggestion import duplicate_checker
from app.suggestion import service as suggestion_service
from app.suggestion.schemas import (
    DuplicateDecision,
    RuleSuggestionDraftContextTerm,
    RuleSuggestionDraftPayload,
    RuleSuggestionDraftRule,
)


class _ExecResult:
    def __init__(self, rows: list[Rule]) -> None:
        self._rows = rows

    def first(self) -> Rule | None:
        return self._rows[0] if self._rows else None


class _FakeRuleSession:
    def __init__(self) -> None:
        self.rules: list[Rule] = []

    def add(self, obj: object) -> None:
        if isinstance(obj, Rule):
            exists = any(r.id == obj.id for r in self.rules)
            if not exists:
                if getattr(obj, "created_at", None) is None:
                    obj.created_at = datetime.now(timezone.utc)
                self.rules.append(obj)

    def flush(self) -> None:
        return None

    def exec(self, stmt: object) -> _ExecResult:
        if getattr(getattr(stmt, "_raw_columns", [None])[0], "name", "") != "rules":
            return _ExecResult([])

        rows = list(self.rules)
        where_criteria = list(getattr(stmt, "_where_criteria", ()))
        for criterion in where_criteria:
            left = str(getattr(criterion, "left", "")).strip().lower()
            expr_text = str(criterion).strip().lower()
            right = getattr(criterion, "right", None)
            value = getattr(right, "value", None) if right is not None else None

            if left.endswith("rules.company_id"):
                if "is null" in expr_text:
                    rows = [r for r in rows if r.company_id is None]
                elif value is not None:
                    rows = [r for r in rows if str(r.company_id) == str(value)]
            elif left.endswith("rules.stable_key") and value is not None:
                rows = [r for r in rows if str(r.stable_key) == str(value)]

        rows.sort(key=lambda r: getattr(r, "created_at", datetime.min), reverse=True)
        return _ExecResult(rows)


def _draft(
    *,
    stable_key: str,
    action: RuleAction = RuleAction.mask,
    term: str | None = None,
    entity_type: str = "INTERNAL_CODE",
) -> RuleSuggestionDraftPayload:
    context_terms = []
    if term is not None:
        context_terms = [
            RuleSuggestionDraftContextTerm(
                entity_type=entity_type,
                term=term,
                lang="vi",
                weight=1.0,
                window_1=60,
                window_2=20,
                enabled=True,
            )
        ]

    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key=stable_key,
            name="Mask literal token",
            description="test",
            scope=RuleScope.prompt,
            conditions={"all": [{"signal": {"field": "context_keywords", "any_of": [term or "phone"]}}]},
            action=action,
            severity=RuleSeverity.medium,
            priority=100,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=context_terms,
    )


def test_literal_specific_stable_key_has_fingerprint_and_is_deterministic() -> None:
    draft = _draft(
        stable_key="personal.custom.mask.internal_code",
        term="thuy-dt-123",
        entity_type="INTERNAL_CODE",
    )

    assert suggestion_service.is_literal_specific(draft) is True

    out_1 = suggestion_service._ensure_company_stable_key(
        prompt="mask ma thuy-dt-123",
        draft=draft,
    )
    out_2 = suggestion_service._ensure_company_stable_key(
        prompt="yeu cau khac nhung cung literal thuy-dt-123",
        draft=draft,
    )

    key_1 = out_1.rule.stable_key
    key_2 = out_2.rule.stable_key
    assert key_1 == key_2
    assert re.match(r"^personal\.secret\.internal_code\.mask\.[0-9a-f]{8}$", key_1)


def test_two_different_literals_generate_different_fingerprint_keys() -> None:
    draft_a = _draft(
        stable_key="personal.custom.mask.internal_code",
        term="thuy-dt-123",
        entity_type="INTERNAL_CODE",
    )
    draft_b = _draft(
        stable_key="personal.custom.mask.internal_code",
        term="1234-xxx-yyy",
        entity_type="INTERNAL_CODE",
    )

    key_a = suggestion_service._ensure_company_stable_key(
        prompt="mask ma thuy-dt-123",
        draft=draft_a,
    ).rule.stable_key
    key_b = suggestion_service._ensure_company_stable_key(
        prompt="mask ma 1234-xxx-yyy",
        draft=draft_b,
    ).rule.stable_key

    assert key_a != key_b


def test_generic_rule_keeps_family_style_key_without_fingerprint() -> None:
    draft = _draft(
        stable_key="phone.mask.policy",
        term="phone number",
        entity_type="PHONE",
    )

    assert suggestion_service.is_literal_specific(draft) is False

    out = suggestion_service._ensure_company_stable_key(
        prompt="mask phone number",
        draft=draft,
    )
    assert out.rule.stable_key == "personal.custom.phone.mask.policy"


def test_apply_rule_draft_creates_two_rules_for_two_literal_fingerprint_keys() -> None:
    session = _FakeRuleSession()
    company_id = uuid4()
    actor_user_id = uuid4()

    draft_a = _draft(
        stable_key="personal.custom.mask.internal_code",
        term="thuy-dt-123",
        entity_type="INTERNAL_CODE",
    )
    draft_b = _draft(
        stable_key="personal.custom.mask.internal_code",
        term="1234-xxx-yyy",
        entity_type="INTERNAL_CODE",
    )

    key_a = suggestion_service._ensure_company_stable_key(
        prompt="mask ma thuy-dt-123",
        draft=draft_a,
    ).rule.stable_key
    key_b = suggestion_service._ensure_company_stable_key(
        prompt="mask ma 1234-xxx-yyy",
        draft=draft_b,
    ).rule.stable_key
    assert key_a != key_b

    row_a = suggestion_service._apply_rule_draft(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        rule_draft=draft_a.rule.model_copy(update={"stable_key": key_a}),
    )
    row_b = suggestion_service._apply_rule_draft(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        rule_draft=draft_b.rule.model_copy(update={"stable_key": key_b}),
    )

    company_rows = [r for r in session.rules if str(r.company_id) == str(company_id)]
    assert len(company_rows) == 2
    assert {str(r.stable_key) for r in company_rows} == {key_a, key_b}
    assert isinstance(row_a.id, UUID)
    assert isinstance(row_b.id, UUID)
    assert row_a.id != row_b.id


def test_duplicate_check_marks_exact_same_literal_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeRuleSession()
    company_id = uuid4()
    draft = _draft(
        stable_key="personal.custom.mask.internal_code",
        term="dt-thuy-1234",
        entity_type="INTERNAL_CODE",
    )
    aligned = suggestion_service._ensure_company_stable_key(
        prompt="mask ma dt-thuy-1234",
        draft=draft,
    )
    existing = Rule(
        company_id=company_id,
        stable_key=aligned.rule.stable_key,
        name=aligned.rule.name,
        description=aligned.rule.description,
        scope=aligned.rule.scope,
        conditions=aligned.rule.conditions,
        conditions_version=1,
        action=aligned.rule.action,
        severity=aligned.rule.severity,
        priority=aligned.rule.priority,
        rag_mode=aligned.rule.rag_mode,
        enabled=aligned.rule.enabled,
        created_by=uuid4(),
    )
    session.add(existing)
    monkeypatch.setattr(
        duplicate_checker,
        "_should_call_llm_for_duplicate",
        lambda **_kwargs: False,
    )

    out = duplicate_checker.build_duplicate_check(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        draft_rule=aligned.rule,
    )

    assert out.decision == DuplicateDecision.exact_duplicate


def test_duplicate_check_downgrades_slight_literal_change_from_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeRuleSession()
    company_id = uuid4()
    existing_draft = _draft(
        stable_key="personal.custom.mask.internal_code",
        term="dt-thuy-1234",
        entity_type="INTERNAL_CODE",
    )
    variant_draft = _draft(
        stable_key="personal.custom.mask.internal_code",
        term="dt-thuy-12345",
        entity_type="INTERNAL_CODE",
    )
    existing_aligned = suggestion_service._ensure_company_stable_key(
        prompt="mask ma dt-thuy-1234",
        draft=existing_draft,
    )
    variant_aligned = suggestion_service._ensure_company_stable_key(
        prompt="mask ma dt-thuy-12345",
        draft=variant_draft,
    )
    existing = Rule(
        company_id=company_id,
        stable_key=existing_aligned.rule.stable_key,
        name=existing_aligned.rule.name,
        description=existing_aligned.rule.description,
        scope=existing_aligned.rule.scope,
        conditions=existing_aligned.rule.conditions,
        conditions_version=1,
        action=existing_aligned.rule.action,
        severity=existing_aligned.rule.severity,
        priority=existing_aligned.rule.priority,
        rag_mode=existing_aligned.rule.rag_mode,
        enabled=existing_aligned.rule.enabled,
        created_by=uuid4(),
    )
    session.add(existing)
    monkeypatch.setattr(
        duplicate_checker,
        "_should_call_llm_for_duplicate",
        lambda **_kwargs: False,
    )

    out = duplicate_checker.build_duplicate_check(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        draft_rule=variant_aligned.rule,
    )

    assert out.decision != DuplicateDecision.exact_duplicate
