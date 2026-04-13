from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.db import all_models as _all_models  # noqa: F401
from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity
from app.common.errors import AppError
from app.rule.schemas import RuleContextTermIn
from app.suggestion import service as suggestion_service
from app.suggestion.schemas import (
    DuplicateDecision,
    RuleDuplicateCheckOut,
    RuleSuggestionApplyIn,
    RuleSuggestionConfirmIn,
    RuleSuggestionDraftContextTerm,
    RuleSuggestionDraftPayload,
    RuleSuggestionDraftRule,
    RuleSuggestionEditIn,
    RuleSuggestionGenerateIn,
    RuleSuggestionRejectIn,
    RuleSuggestionSimulateIn,
    SuggestionStatus,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _duplicate_check_out() -> RuleDuplicateCheckOut:
    return RuleDuplicateCheckOut(
        decision=DuplicateDecision.different,
        confidence=0.9,
        rationale="unit_test",
        matched_rule_ids=[],
        candidates=[],
        top_k=5,
        exact_threshold=0.92,
        near_threshold=0.82,
        source="unit_test",
        llm_provider=None,
        llm_model=None,
        llm_fallback_used=False,
    )


def _draft_custom_secret() -> RuleSuggestionDraftPayload:
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key="personal.custom.manual.mask_internal_code",
            name="Mask internal token",
            description="Mask ZXQ-UNSEEN-9981",
            scope=RuleScope.prompt,
            conditions={
                "all": [
                    {
                        "signal": {
                            "field": "context_keywords",
                            "any_of": ["zxq-unseen-9981"],
                        }
                    }
                ]
            },
            action=RuleAction.mask,
            severity=RuleSeverity.medium,
            priority=80,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[
            RuleSuggestionDraftContextTerm(
                entity_type="INTERNAL_CODE",
                term="zxq-unseen-9981",
                lang="vi",
                weight=1.0,
                window_1=60,
                window_2=20,
                enabled=True,
            )
        ],
    )


def _draft_internal_code_exact_token(token: str = "zxq-thuydt123-1989") -> RuleSuggestionDraftPayload:
    normalized = str(token).strip().lower()
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key="personal.custom.manual.mask_internal_code",
            name=f"Mask internal token {normalized}",
            description=f"Mask {normalized}",
            scope=RuleScope.prompt,
            conditions={
                "all": [
                    {
                        "signal": {
                            "field": "context_keywords",
                            "any_of": [normalized],
                        }
                    }
                ]
            },
            action=RuleAction.mask,
            severity=RuleSeverity.medium,
            priority=80,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[
            RuleSuggestionDraftContextTerm(
                entity_type="INTERNAL_CODE",
                term=normalized,
                lang="vi",
                weight=1.0,
                window_1=60,
                window_2=20,
                enabled=True,
            )
        ],
    )


def _draft_payroll_external_email() -> RuleSuggestionDraftPayload:
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key="personal.custom.manual.block_payroll_external_email",
            name="Block payroll to personal email",
            description="Block payroll/salary sharing to personal email like gmail",
            scope=RuleScope.prompt,
            conditions={
                "all": [
                    {
                        "signal": {
                            "field": "context_keywords",
                            "any_of": ["payroll", "salary", "luong"],
                        }
                    },
                    {
                        "signal": {
                            "field": "context_keywords",
                            "any_of": ["gmail", "personal email", "external email"],
                        }
                    },
                ]
            },
            action=RuleAction.block,
            severity=RuleSeverity.high,
            priority=120,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[
            RuleSuggestionDraftContextTerm(entity_type="PERSONA_OFFICE", term="payroll", lang="vi"),
            RuleSuggestionDraftContextTerm(entity_type="PERSONA_OFFICE", term="gmail", lang="vi"),
        ],
    )


def _draft_common_pii_email() -> RuleSuggestionDraftPayload:
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key="personal.custom.manual.mask_personal_email",
            name="Mask personal email",
            description="Mask EMAIL entity",
            scope=RuleScope.prompt,
            conditions={"any": [{"entity_type": "EMAIL"}]},
            action=RuleAction.mask,
            severity=RuleSeverity.medium,
            priority=70,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[],
    )


def _draft_heuristic_abstract() -> RuleSuggestionDraftPayload:
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key="personal.custom.manual.office_abstract",
            name="Office abstract mask",
            description="Heuristic-assisted abstract draft",
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
            priority=60,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[],
    )


def _draft_business_context_semantic() -> RuleSuggestionDraftPayload:
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key="personal.custom.business.trung_tam_m.block",
            name="Chan tai lieu noi bo cua Trung tam M",
            description="semantic business phrase draft",
            scope=RuleScope.chat,
            conditions={
                "all": [
                    {
                        "signal": {
                            "field": "context_keywords",
                            "any_of": ["trung tam m"],
                        }
                    }
                ]
            },
            action=RuleAction.block,
            severity=RuleSeverity.high,
            priority=120,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[
            RuleSuggestionDraftContextTerm(
                entity_type="CUSTOM_SECRET",
                term="tai lieu noi bo",
                lang="vi",
                weight=1.0,
                window_1=60,
                window_2=20,
                enabled=True,
            )
        ],
    )


class _ExecResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)

    def first(self) -> object | None:
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self) -> None:
        self.suggestions: dict[str, object] = {}
        self.logs: list[object] = []
        self.rules: dict[str, object] = {}
        self.context_terms: dict[str, object] = {}

    def add(self, obj: object) -> None:
        now = _now()
        if hasattr(obj, "nl_input") and hasattr(obj, "draft_json") and hasattr(obj, "dedupe_key"):
            if getattr(obj, "id", None) is None:
                setattr(obj, "id", uuid4())
            if getattr(obj, "created_at", None) is None:
                setattr(obj, "created_at", now)
            setattr(obj, "updated_at", now)
            self.suggestions[str(getattr(obj, "id"))] = obj
            return
        if hasattr(obj, "suggestion_id") and hasattr(obj, "action"):
            if getattr(obj, "id", None) is None:
                setattr(obj, "id", uuid4())
            if getattr(obj, "created_at", None) is None:
                setattr(obj, "created_at", now)
            self.logs.append(obj)
            return
        if hasattr(obj, "stable_key") and hasattr(obj, "conditions"):
            if getattr(obj, "id", None) is None:
                setattr(obj, "id", uuid4())
            self.rules[str(getattr(obj, "id"))] = obj
            return
        if hasattr(obj, "entity_type") and hasattr(obj, "term"):
            if getattr(obj, "id", None) is None:
                setattr(obj, "id", uuid4())
            self.context_terms[str(getattr(obj, "id"))] = obj

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def refresh(self, _obj: object) -> None:
        return None

    def rollback(self) -> None:
        return None

    def get(self, model: object, key: UUID) -> object | None:
        if str(getattr(model, "__name__", "")) == "RuleSuggestion":
            return self.suggestions.get(str(key))
        return None

    def exec(self, stmt: object) -> _ExecResult:
        entity_name = _entity_name(stmt)
        filters = _extract_stmt_filters(stmt)
        limit = _extract_stmt_limit(stmt)

        if entity_name == "RuleSuggestion":
            rows = list(self.suggestions.values())
            company_id = filters.get("company_id")
            if company_id is not None:
                rows = [r for r in rows if str(getattr(r, "company_id")) == str(company_id)]
            dedupe_key = filters.get("dedupe_key")
            if dedupe_key is not None:
                rows = [r for r in rows if str(getattr(r, "dedupe_key")) == str(dedupe_key)]
            status_filter = filters.get("status")
            if isinstance(status_filter, list):
                rows = [r for r in rows if str(getattr(r, "status")) in status_filter]
            elif status_filter is not None:
                rows = [r for r in rows if str(getattr(r, "status")) == str(status_filter)]
            rows = sorted(rows, key=lambda x: getattr(x, "created_at"), reverse=True)
            if limit is not None:
                rows = rows[:limit]
            return _ExecResult(rows)

        if entity_name == "RuleSuggestionLog":
            rows = list(self.logs)
            suggestion_id = filters.get("suggestion_id")
            if suggestion_id is not None:
                rows = [r for r in rows if str(getattr(r, "suggestion_id")) == str(suggestion_id)]
            action = filters.get("action")
            if action is not None:
                rows = [r for r in rows if str(getattr(r, "action")) == str(action)]
            rows = sorted(rows, key=lambda x: getattr(x, "created_at"), reverse=True)
            if limit is not None:
                rows = rows[:limit]
            return _ExecResult(rows)

        return _ExecResult([])


def _entity_name(stmt: object) -> str:
    raw_columns = getattr(stmt, "_raw_columns", None)
    if not isinstance(raw_columns, list) or not raw_columns:
        return ""
    first = raw_columns[0]
    table_name = str(getattr(first, "name", ""))
    if table_name == "rule_suggestions":
        return "RuleSuggestion"
    if table_name == "rule_suggestion_logs":
        return "RuleSuggestionLog"
    return ""


def _extract_stmt_limit(stmt: object) -> int | None:
    limit_clause = getattr(stmt, "_limit_clause", None)
    if limit_clause is None:
        return None
    value = getattr(limit_clause, "value", None)
    if isinstance(value, int):
        return int(value)
    return None


def _extract_stmt_filters(stmt: object) -> dict[str, object]:
    out: dict[str, object] = {}
    for criterion in getattr(stmt, "_where_criteria", ()):
        left = getattr(criterion, "left", None)
        right = getattr(criterion, "right", None)
        if left is None or right is None:
            continue
        field = str(left).split(".")[-1].strip()
        if not field:
            continue
        value = getattr(right, "value", None)
        if value is None:
            continue
        out[field] = value
    return out


def _patch_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(suggestion_service, "_load_company_or_404", lambda **_kwargs: None)
    monkeypatch.setattr(suggestion_service, "_require_company_admin", lambda **_kwargs: None)
    monkeypatch.setattr(suggestion_service, "build_duplicate_check", lambda **_kwargs: _duplicate_check_out())
    monkeypatch.setattr(suggestion_service, "_append_log", _append_log_memory)


def _case_meta(*, has_policy_context: bool) -> dict[str, object]:
    policy_ids = ["p_12"] if has_policy_context else []
    return {
        "source": "llm",
        "provider": "mock",
        "model": "mock-model",
        "fallback_used": False,
        "context_retrieval": {
            "has_policy_context": has_policy_context,
            "policy_chunk_ids": policy_ids,
            "related_rule_ids": ["r_101"],
            "policy_chunks": 1 if has_policy_context else 0,
            "related_rules": 1,
        },
    }


def _append_log_memory(
    *,
    session: _FakeSession,
    suggestion_id: UUID,
    company_id: UUID,
    actor_user_id: UUID,
    action: str,
    reason: str | None = None,
    before_json: dict[str, object] | None = None,
    after_json: dict[str, object] | None = None,
) -> None:
    session.logs.append(
        SimpleNamespace(
            id=uuid4(),
            suggestion_id=suggestion_id,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action=action,
            reason=(reason or "").strip() or None,
            before_json=before_json,
            after_json=after_json,
            created_at=_now(),
        )
    )


def _wire_generate_from_prompt(
    monkeypatch: pytest.MonkeyPatch,
    by_prompt: dict[str, tuple[RuleSuggestionDraftPayload, dict[str, object]]],
) -> None:
    def _fake_generate_draft_from_prompt(**kwargs: object) -> tuple[RuleSuggestionDraftPayload, dict[str, object]]:
        prompt = str(kwargs.get("prompt") or "")
        return by_prompt[prompt]

    monkeypatch.setattr(
        suggestion_service,
        "_generate_draft_from_prompt",
        _fake_generate_draft_from_prompt,
    )


@pytest.mark.parametrize(
    "prompt,draft,meta,expect_runtime_usable",
    [
        (
            "Tạo rule mask mã nội bộ ZXQ-UNSEEN-9981",
            _draft_custom_secret(),
            _case_meta(has_policy_context=False),
            True,
        ),
        (
            "Tạo rule block gửi danh sách lương payroll ra email cá nhân như gmail",
            _draft_payroll_external_email(),
            _case_meta(has_policy_context=True),
            True,
        ),
        (
            "Tạo rule mask email cá nhân",
            _draft_common_pii_email(),
            _case_meta(has_policy_context=False),
            True,
        ),
        (
            "Tạo rule mask thông tin hợp đồng nội bộ trong ngữ cảnh office",
            _draft_heuristic_abstract(),
            _case_meta(has_policy_context=False),
            False,
        ),
    ],
)
def test_round1_generate_shape_for_intent_groups(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    draft: RuleSuggestionDraftPayload,
    meta: dict[str, object],
    expect_runtime_usable: bool,
) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(monkeypatch, {prompt: (draft, meta)})

    result = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt=prompt),
    )

    assert result.status == SuggestionStatus.draft
    assert result.explanation.summary
    assert result.explanation.detected_intent
    assert result.explanation.action_reason
    assert 0.0 <= result.quality_signals.intent_confidence <= 1.0
    assert result.quality_signals.conflict_risk == "unknown"
    assert isinstance(result.quality_signals.runtime_warnings, list)
    assert result.quality_signals.runtime_usable is expect_runtime_usable
    if not expect_runtime_usable:
        assert "abstract_context_keywords_not_runtime_usable" in result.quality_signals.runtime_warnings
    assert isinstance(result.retrieval_context.policy_chunk_ids, list)
    assert isinstance(result.retrieval_context.related_rule_ids, list)
    assert result.duplicate_check.decision in {
        DuplicateDecision.different,
        DuplicateDecision.near_duplicate,
        DuplicateDecision.exact_duplicate,
    }


def test_round1_get_and_list_filter_by_status(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)

    by_prompt = {
        "A": (_draft_custom_secret(), _case_meta(has_policy_context=False)),
        "B": (_draft_payroll_external_email(), _case_meta(has_policy_context=True)),
        "C": (_draft_common_pii_email(), _case_meta(has_policy_context=False)),
        "D": (_draft_heuristic_abstract(), _case_meta(has_policy_context=False)),
    }
    _wire_generate_from_prompt(monkeypatch, by_prompt)

    generated = [
        suggestion_service.generate_rule_suggestion(
            session=session,  # type: ignore[arg-type]
            company_id=company_id,
            actor_user_id=actor_user_id,
            payload=RuleSuggestionGenerateIn(prompt=p),
        )
        for p in ["A", "B", "C", "D"]
    ]
    rows = list(session.suggestions.values())
    rows[1].status = SuggestionStatus.approved.value
    rows[2].status = SuggestionStatus.applied.value
    rows[3].status = SuggestionStatus.rejected.value

    got = suggestion_service.get_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated[0].id,
        actor_user_id=actor_user_id,
    )
    assert got.id == generated[0].id
    assert got.explanation.summary
    assert got.quality_signals.generation_source

    for status in [
        SuggestionStatus.draft,
        SuggestionStatus.approved,
        SuggestionStatus.applied,
        SuggestionStatus.rejected,
    ]:
        listed = suggestion_service.list_rule_suggestions(
            session=session,  # type: ignore[arg-type]
            company_id=company_id,
            actor_user_id=actor_user_id,
            status=status,
            limit=50,
        )
        assert listed
        assert all(x.status == status for x in listed)


def test_round1_edit_draft_with_version_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {"edit_prompt": (_draft_common_pii_email(), _case_meta(has_policy_context=False))},
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="edit_prompt"),
    )

    draft = generated.draft.model_copy(deep=True)
    draft.rule.name = "Updated name from edit"
    edited = suggestion_service.edit_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionEditIn(draft=draft, expected_version=1),
    )
    assert edited.version == 2
    assert edited.draft.rule.name == "Updated name from edit"

    with pytest.raises(AppError) as stale_err:
        suggestion_service.edit_rule_suggestion(
            session=session,  # type: ignore[arg-type]
            company_id=company_id,
            suggestion_id=generated.id,
            actor_user_id=actor_user_id,
            payload=RuleSuggestionEditIn(draft=draft, expected_version=1),
        )
    assert stale_err.value.status_code == 409

    row = session.suggestions[str(generated.id)]
    row.status = SuggestionStatus.approved.value
    with pytest.raises(AppError) as status_err:
        suggestion_service.edit_rule_suggestion(
            session=session,  # type: ignore[arg-type]
            company_id=company_id,
            suggestion_id=generated.id,
            actor_user_id=actor_user_id,
            payload=RuleSuggestionEditIn(draft=draft, expected_version=2),
        )
    assert status_err.value.status_code == 422


def test_round1_edit_literal_specific_draft_realigns_conditions_and_stable_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {
            "literal_prompt": (
                _draft_internal_code_exact_token("dt-thuy-1234"),
                _case_meta(has_policy_context=False),
            )
        },
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="literal_prompt"),
    )

    draft = generated.draft.model_copy(deep=True)
    draft.context_terms[0].term = "dt-thuy-12345"

    edited = suggestion_service.edit_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionEditIn(draft=draft, expected_version=1),
    )

    condition_terms = suggestion_service._collect_context_keyword_terms(
        edited.draft.rule.conditions
    )
    assert edited.draft.rule.stable_key != generated.draft.rule.stable_key
    assert "dt-thuy-12345" in condition_terms
    assert "dt-thuy-1234" not in condition_terms
    assert (
        edited.draft.rule.stable_key
        == suggestion_service._build_literal_specific_stable_key(edited.draft)
    )


def test_round1_confirm_realigns_literal_specific_draft_before_duplicate_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {
            "literal_confirm_prompt": (
                _draft_internal_code_exact_token("dt-thuy-1234"),
                _case_meta(has_policy_context=False),
            )
        },
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="literal_confirm_prompt"),
    )

    row = session.suggestions[str(generated.id)]
    stale_draft = generated.draft.model_copy(deep=True)
    stale_draft.context_terms[0].term = "dt-thuy-12345"
    row.draft_json = stale_draft.model_dump(mode="json")

    captured: dict[str, object] = {}

    def _capture_duplicate_check(**kwargs: object) -> RuleDuplicateCheckOut:
        draft_rule = kwargs["draft_rule"]
        captured["stable_key"] = draft_rule.stable_key
        captured["conditions"] = draft_rule.conditions
        return _duplicate_check_out()

    monkeypatch.setattr(suggestion_service, "build_duplicate_check", _capture_duplicate_check)

    confirmed = suggestion_service.confirm_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionConfirmIn(reason="literal edit ok", expected_version=1),
    )

    condition_terms = suggestion_service._collect_context_keyword_terms(
        captured["conditions"]
    )
    assert confirmed.status == SuggestionStatus.approved
    assert "dt-thuy-12345" in condition_terms
    assert "dt-thuy-1234" not in condition_terms
    assert str(captured["stable_key"]) == str(row.draft_json["rule"]["stable_key"])
    assert str(captured["stable_key"]) != generated.draft.rule.stable_key


def test_round1_confirm_apply_and_apply_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {
            "apply_prompt": (_draft_custom_secret(), _case_meta(has_policy_context=False)),
            "apply_negative_prompt": (_draft_common_pii_email(), _case_meta(has_policy_context=False)),
        },
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="apply_prompt"),
    )

    confirmed = suggestion_service.confirm_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionConfirmIn(reason="ok", expected_version=1),
    )
    assert confirmed.status == SuggestionStatus.approved
    assert confirmed.version == 2

    fake_rule_id = uuid4()
    fake_manual_context_term_ids = [uuid4()]
    fake_auto_context_term_ids = [uuid4()]
    sync_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        suggestion_service,
        "_apply_rule_draft",
        lambda **_kwargs: SimpleNamespace(
            id=fake_rule_id,
            stable_key="personal.custom.manual.mask_internal_code",
            name="Mask internal token",
            action=RuleAction.mask,
        ),
    )
    monkeypatch.setattr(
        suggestion_service,
        "_apply_context_terms",
        lambda **_kwargs: list(fake_manual_context_term_ids),
    )
    monkeypatch.setattr(
        suggestion_service,
        "_build_auto_context_terms_from_conditions",
        lambda **_kwargs: [
            RuleContextTermIn(
                entity_type="CUSTOM_SECRET",
                term="zxq-unseen-9981",
                lang="vi",
                weight=1.0,
                window_1=60,
                window_2=20,
                enabled=True,
            )
        ],
    )
    monkeypatch.setattr(
        suggestion_service,
        "_upsert_company_context_terms",
        lambda **_kwargs: list(fake_auto_context_term_ids),
    )
    monkeypatch.setattr(
        suggestion_service,
        "_sync_rule_context_term_links",
        lambda **kwargs: sync_calls.append(dict(kwargs)),
    )
    invalidated_context_company_ids: list[UUID | None] = []
    monkeypatch.setattr(
        suggestion_service,
        "invalidate_context_runtime_cache",
        lambda company_id: invalidated_context_company_ids.append(company_id),
    )
    invalidated_company_ids: list[UUID | None] = []
    monkeypatch.setattr(
        suggestion_service.RuleEngine,
        "invalidate_cache",
        lambda company_id=None, user_id=None: invalidated_company_ids.append(company_id),
    )

    applied = suggestion_service.apply_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionApplyIn(expected_version=2),
    )
    assert applied.rule_id == fake_rule_id
    assert applied.context_term_ids == [
        *fake_manual_context_term_ids,
        *fake_auto_context_term_ids,
    ]
    assert sync_calls == [
        {
            "session": session,
            "rule_id": fake_rule_id,
            "context_term_ids": fake_manual_context_term_ids,
            "source": "manual",
        },
        {
            "session": session,
            "rule_id": fake_rule_id,
            "context_term_ids": fake_auto_context_term_ids,
            "source": "auto",
        },
    ]

    row = session.suggestions[str(generated.id)]
    assert row.status == SuggestionStatus.applied.value
    assert isinstance(row.applied_result_json, dict)
    assert str(row.applied_result_json.get("rule_id") or "") == str(fake_rule_id)
    assert invalidated_context_company_ids == [company_id]
    assert invalidated_company_ids == [company_id]

    applied_again = suggestion_service.apply_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionApplyIn(expected_version=3),
    )
    assert applied_again.rule_id == fake_rule_id
    assert applied_again.context_term_ids == [
        *fake_manual_context_term_ids,
        *fake_auto_context_term_ids,
    ]
    assert invalidated_context_company_ids == [company_id]
    assert invalidated_company_ids == [company_id]

    negative_generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="apply_negative_prompt"),
    )
    draft_row = session.suggestions[str(negative_generated.id)]
    with pytest.raises(AppError) as not_approved_err:
        suggestion_service.apply_rule_suggestion(
            session=session,  # type: ignore[arg-type]
            company_id=company_id,
            suggestion_id=negative_generated.id,
            actor_user_id=actor_user_id,
            payload=RuleSuggestionApplyIn(expected_version=1),
        )
    assert not_approved_err.value.status_code == 422


def test_round1_apply_syncs_empty_manual_links_when_draft_has_no_context_terms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    draft = RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key="personal.custom.manual.target_only",
            name="Target only rule",
            description="auto terms should still materialize",
            scope=RuleScope.chat,
            conditions={
                "all": [
                    {
                        "signal": {
                            "field": "context_keywords",
                            "any_of": ["truong nhom q"],
                        }
                    }
                ]
            },
            action=RuleAction.block,
            severity=RuleSeverity.high,
            priority=120,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[],
    )
    _wire_generate_from_prompt(
        monkeypatch,
        {"apply_no_manual_terms_prompt": (draft, _case_meta(has_policy_context=False))},
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="apply_no_manual_terms_prompt"),
    )
    suggestion_service.confirm_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionConfirmIn(reason="ok", expected_version=1),
    )

    fake_rule_id = uuid4()
    fake_auto_context_term_ids = [uuid4()]
    sync_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        suggestion_service,
        "_apply_rule_draft",
        lambda **_kwargs: SimpleNamespace(
            id=fake_rule_id,
            stable_key="personal.custom.manual.target_only",
            name="Target only rule",
            action=RuleAction.block,
        ),
    )
    monkeypatch.setattr(
        suggestion_service,
        "_apply_context_terms",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr(
        suggestion_service,
        "_build_auto_context_terms_from_conditions",
        lambda **_kwargs: [
            RuleContextTermIn(
                entity_type="CUSTOM_SECRET",
                term="truong nhom q",
                lang="vi",
                weight=1.0,
                window_1=60,
                window_2=20,
                enabled=True,
            )
        ],
    )
    monkeypatch.setattr(
        suggestion_service,
        "_upsert_company_context_terms",
        lambda **_kwargs: list(fake_auto_context_term_ids),
    )
    monkeypatch.setattr(
        suggestion_service,
        "_sync_rule_context_term_links",
        lambda **kwargs: sync_calls.append(dict(kwargs)),
    )
    monkeypatch.setattr(
        suggestion_service,
        "invalidate_context_runtime_cache",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        suggestion_service.RuleEngine,
        "invalidate_cache",
        lambda *args, **kwargs: None,
    )

    applied = suggestion_service.apply_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionApplyIn(expected_version=2),
    )

    assert applied.context_term_ids == fake_auto_context_term_ids
    assert sync_calls == [
        {
            "session": session,
            "rule_id": fake_rule_id,
            "context_term_ids": [],
            "source": "manual",
        },
        {
            "session": session,
            "rule_id": fake_rule_id,
            "context_term_ids": fake_auto_context_term_ids,
            "source": "auto",
        },
    ]


def test_round1_reject_and_status_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {"reject_prompt": (_draft_payroll_external_email(), _case_meta(has_policy_context=True))},
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="reject_prompt"),
    )

    rejected = suggestion_service.reject_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionRejectIn(reason="not suitable", expected_version=1),
    )
    assert rejected.status == SuggestionStatus.rejected
    assert rejected.version == 2

    row = session.suggestions[str(generated.id)]
    assert row.reject_reason == "not suitable"
    row.status = SuggestionStatus.applied.value
    with pytest.raises(AppError) as invalid_status_err:
        suggestion_service.reject_rule_suggestion(
            session=session,  # type: ignore[arg-type]
            company_id=company_id,
            suggestion_id=generated.id,
            actor_user_id=actor_user_id,
            payload=RuleSuggestionRejectIn(reason="cannot reject applied", expected_version=2),
        )
    assert invalid_status_err.value.status_code == 422


def test_round1_simulate_contract_for_draft_and_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {"simulate_prompt": (_draft_custom_secret(), _case_meta(has_policy_context=False))},
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="simulate_prompt"),
    )
    row = session.suggestions[str(generated.id)]

    monkeypatch.setattr(
        suggestion_service,
        "load_context_runtime_overrides",
        lambda **_kwargs: SimpleNamespace(regex_hints={}, persona_keywords={}),
    )
    monkeypatch.setattr(
        suggestion_service,
        "_build_simulation_runtime_rules",
        lambda **_kwargs: [
            suggestion_service.RuleRuntime(
                rule_id=uuid4(),
                stable_key="personal.custom.manual.mask_internal_code",
                name="simulate runtime rule",
                action=RuleAction.mask,
                priority=100,
                conditions={},
            )
        ],
    )

    class _FakeDetector:
        def scan(self, _text: str, context_hints_by_entity: object | None = None) -> list[object]:
            _ = context_hints_by_entity
            return []

    class _FakeScorer:
        def score(self, text: str, persona_keywords_override: object | None = None) -> dict[str, str]:
            _ = persona_keywords_override
            return {"raw_text": text}

        def to_signals_dict(self, ctx: dict[str, str]) -> dict[str, str]:
            return {"raw_text": ctx.get("raw_text", "")}

    class _FakeResolver:
        def resolve(self, matches: list[object]) -> SimpleNamespace:
            return SimpleNamespace(final_action=RuleAction.mask if matches else RuleAction.allow)

    monkeypatch.setattr(suggestion_service, "_SIMULATE_DETECTOR", _FakeDetector())
    monkeypatch.setattr(suggestion_service, "_SIMULATE_CONTEXT_SCORER", _FakeScorer())
    monkeypatch.setattr(suggestion_service, "_SIMULATE_RESOLVER", _FakeResolver())

    def _fake_eval(**kwargs: object) -> list[object]:
        signals = kwargs.get("signals") or {}
        text = str((signals or {}).get("raw_text") or "").lower()
        if "zxq-unseen-9981" not in text:
            return []
        return [
            suggestion_service.RuleMatch(
                rule_id=uuid4(),
                stable_key="personal.custom.manual.mask_internal_code",
                name="simulate runtime rule",
                action=RuleAction.mask,
                priority=100,
            )
        ]

    monkeypatch.setattr(suggestion_service, "_evaluate_with_runtime_rules", _fake_eval)

    simulate_draft = suggestion_service.simulate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionSimulateIn(
            samples=["Toi co ma zxq-unseen-9981"],
            include_examples=True,
        ),
    )
    assert simulate_draft.suggestion_id == generated.id
    assert simulate_draft.sample_size == 1
    assert isinstance(simulate_draft.runtime_usable, bool)
    assert isinstance(simulate_draft.runtime_warnings, list)
    assert simulate_draft.matched_count == 1
    assert simulate_draft.action_breakdown == {"ALLOW": 0, "MASK": 1, "BLOCK": 0}
    assert len(simulate_draft.results) == 1
    assert simulate_draft.results[0].content == "Toi co ma zxq-unseen-9981"
    assert simulate_draft.results[0].matched is True
    assert simulate_draft.results[0].predicted_action == "MASK"
    assert len(session.rules) == 0

    row.status = SuggestionStatus.approved.value
    simulate_approved = suggestion_service.simulate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionSimulateIn(
            samples=["Toi co ma zxq-unseen-9981", "seed no match"],
            include_examples=False,
        ),
    )
    assert simulate_approved.sample_size == 2
    assert simulate_approved.matched_count == 1
    assert simulate_approved.action_breakdown == {"ALLOW": 1, "MASK": 1, "BLOCK": 0}
    assert len(simulate_approved.results) == 2
    assert simulate_approved.results[0].content == "Toi co ma zxq-unseen-9981"
    assert simulate_approved.results[0].matched is True
    assert simulate_approved.results[0].predicted_action == "MASK"
    assert simulate_approved.results[1].content == "seed no match"
    assert simulate_approved.results[1].matched is False
    assert simulate_approved.results[1].predicted_action == "ALLOW"

    row.status = SuggestionStatus.applied.value
    with pytest.raises(AppError) as applied_err:
        suggestion_service.simulate_rule_suggestion(
            session=session,  # type: ignore[arg-type]
            company_id=company_id,
            suggestion_id=generated.id,
            actor_user_id=actor_user_id,
            payload=RuleSuggestionSimulateIn(
                samples=["Toi co ma zxq-unseen-9981", "seed no match"],
                include_examples=True,
            ),
        )
    assert applied_err.value.status_code == 422


def test_round1_simulate_merges_draft_exact_terms_into_context_keywords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {
            "simulate_exact_prompt": (
                _draft_internal_code_exact_token("zxq-thuydt123-1989"),
                _case_meta(has_policy_context=False),
            )
        },
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="simulate_exact_prompt"),
    )

    monkeypatch.setattr(
        suggestion_service,
        "load_context_runtime_overrides",
        lambda **_kwargs: SimpleNamespace(regex_hints={}, persona_keywords={}, exact_terms=[]),
    )
    monkeypatch.setattr(
        suggestion_service,
        "_build_simulation_runtime_rules",
        lambda **_kwargs: [
            suggestion_service.RuleRuntime(
                rule_id=uuid4(),
                stable_key="personal.custom.manual.mask_internal_code",
                name="simulate runtime rule",
                action=RuleAction.mask,
                priority=100,
                conditions={},
            )
        ],
    )

    class _FakeDetector:
        def scan(self, _text: str, context_hints_by_entity: object | None = None) -> list[object]:
            _ = context_hints_by_entity
            return []

    class _FakeScorer:
        def score(self, _text: str, persona_keywords_override: object | None = None) -> dict[str, object]:
            _ = persona_keywords_override
            return {"ctx": "ok"}

        def to_signals_dict(self, _ctx: dict[str, object]) -> dict[str, object]:
            # Simulate baseline signals without exact token to validate merge-from-draft.
            return {"context_keywords": []}

    class _FakeResolver:
        def resolve(self, matches: list[object]) -> SimpleNamespace:
            return SimpleNamespace(final_action=RuleAction.mask if matches else RuleAction.allow)

    monkeypatch.setattr(suggestion_service, "_SIMULATE_DETECTOR", _FakeDetector())
    monkeypatch.setattr(suggestion_service, "_SIMULATE_CONTEXT_SCORER", _FakeScorer())
    monkeypatch.setattr(suggestion_service, "_SIMULATE_RESOLVER", _FakeResolver())

    def _fake_eval(**kwargs: object) -> list[object]:
        signals = kwargs.get("signals") or {}
        keywords = {str(x).strip().lower() for x in list((signals or {}).get("context_keywords") or [])}
        if "zxq-thuydt123-1989" not in keywords:
            return []
        return [
            suggestion_service.RuleMatch(
                rule_id=uuid4(),
                stable_key="personal.custom.manual.mask_internal_code",
                name="simulate runtime rule",
                action=RuleAction.mask,
                priority=100,
            )
        ]

    monkeypatch.setattr(suggestion_service, "_evaluate_with_runtime_rules", _fake_eval)

    result = suggestion_service.simulate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionSimulateIn(
            samples=[
                "Toi co ma don zxq-thuydt123-1989, nho kiem tra",
                "Xin chao ban",
            ],
            include_examples=True,
        ),
    )

    assert result.sample_size == 2
    assert result.matched_count == 1
    assert result.action_breakdown == {"ALLOW": 1, "MASK": 1, "BLOCK": 0}
    assert isinstance(result.runtime_usable, bool)
    assert isinstance(result.runtime_warnings, list)
    assert result.results[0].content == "Toi co ma don zxq-thuydt123-1989, nho kiem tra"
    assert result.results[0].matched is True
    assert result.results[0].predicted_action == "MASK"
    assert result.results[1].content == "Xin chao ban"
    assert result.results[1].matched is False
    assert result.results[1].predicted_action == "ALLOW"
    assert len(session.rules) == 0


def test_round1_simulate_internal_code_exact_non_match_returns_allow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {
            "simulate_exact_non_match_prompt": (
                _draft_internal_code_exact_token("zxq-thuydt123-1989"),
                _case_meta(has_policy_context=False),
            )
        },
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="simulate_exact_non_match_prompt"),
    )

    monkeypatch.setattr(
        suggestion_service,
        "load_context_runtime_overrides",
        lambda **_kwargs: SimpleNamespace(regex_hints={}, persona_keywords={}, exact_terms=[]),
    )
    monkeypatch.setattr(
        suggestion_service,
        "_build_simulation_runtime_rules",
        lambda **_kwargs: [
            suggestion_service.RuleRuntime(
                rule_id=uuid4(),
                stable_key="personal.custom.manual.mask_internal_code",
                name="simulate runtime rule",
                action=RuleAction.mask,
                priority=100,
                conditions={},
            )
        ],
    )

    class _FakeDetector:
        def scan(self, _text: str, context_hints_by_entity: object | None = None) -> list[object]:
            _ = context_hints_by_entity
            return []

    class _FakeScorer:
        def score(self, _text: str, persona_keywords_override: object | None = None) -> dict[str, object]:
            _ = persona_keywords_override
            return {"ctx": "ok"}

        def to_signals_dict(self, _ctx: dict[str, object]) -> dict[str, object]:
            return {"context_keywords": []}

    class _FakeResolver:
        def resolve(self, matches: list[object]) -> SimpleNamespace:
            return SimpleNamespace(final_action=RuleAction.mask if matches else RuleAction.allow)

    monkeypatch.setattr(suggestion_service, "_SIMULATE_DETECTOR", _FakeDetector())
    monkeypatch.setattr(suggestion_service, "_SIMULATE_CONTEXT_SCORER", _FakeScorer())
    monkeypatch.setattr(suggestion_service, "_SIMULATE_RESOLVER", _FakeResolver())

    def _fake_eval(**kwargs: object) -> list[object]:
        signals = kwargs.get("signals") or {}
        keywords = {str(x).strip().lower() for x in list((signals or {}).get("context_keywords") or [])}
        if "zxq-thuydt123-1989" not in keywords:
            return []
        return [
            suggestion_service.RuleMatch(
                rule_id=uuid4(),
                stable_key="personal.custom.manual.mask_internal_code",
                name="simulate runtime rule",
                action=RuleAction.mask,
                priority=100,
            )
        ]

    monkeypatch.setattr(suggestion_service, "_evaluate_with_runtime_rules", _fake_eval)

    result = suggestion_service.simulate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionSimulateIn(
            samples=[
                "Xin chao ban",
                "Toi dang hoi lich hop tuan nay",
            ],
            include_examples=True,
        ),
    )

    assert result.sample_size == 2
    assert result.matched_count == 0
    assert result.action_breakdown == {"ALLOW": 2, "MASK": 0, "BLOCK": 0}
    assert all(r.matched is False for r in result.results)
    assert all(r.predicted_action == "ALLOW" for r in result.results)
    assert len(session.rules) == 0


def test_round1_logs_history_has_before_after(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {"log_prompt": (_draft_common_pii_email(), _case_meta(has_policy_context=False))},
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="log_prompt"),
    )

    draft = generated.draft.model_copy(deep=True)
    draft.rule.name = "Edited for log"
    suggestion_service.edit_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionEditIn(draft=draft, expected_version=1),
    )
    suggestion_service.confirm_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionConfirmIn(reason="confirm for log", expected_version=2),
    )

    logs = suggestion_service.list_rule_suggestion_logs(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        limit=50,
    )
    assert logs
    actions = {x.action for x in logs}
    assert "suggestion.create" in actions
    assert "suggestion.generate.telemetry" in actions
    assert "suggestion.edit" in actions
    assert "suggestion.confirm" in actions
    assert any(x.after_json for x in logs)
    assert any(x.before_json for x in logs if x.action in {"suggestion.edit", "suggestion.confirm"})


def test_round1_confirm_allows_business_phrase_with_noi_bo(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {
            "toi muon chan cac noi dung ve tai lieu noi bo cua Trung tam M": (
                _draft_business_context_semantic(),
                _case_meta(has_policy_context=False),
            )
        },
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(
            prompt="toi muon chan cac noi dung ve tai lieu noi bo cua Trung tam M"
        ),
    )

    confirmed = suggestion_service.confirm_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionConfirmIn(reason="ok", expected_version=1),
    )

    assert confirmed.status == SuggestionStatus.approved
    assert confirmed.draft.rule.match_mode.value == "keyword_plus_semantic"
    assert [str(term.term).lower() for term in confirmed.draft.context_terms] == [
        "tai lieu noi bo"
    ]


def test_round1_confirm_allows_true_literal_prompt_but_keeps_runtime_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {
            "Che token noi bo": (
                _draft_heuristic_abstract(),
                _case_meta(has_policy_context=False),
            )
        },
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="Che token noi bo"),
    )

    confirmed = suggestion_service.confirm_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionConfirmIn(reason="ok", expected_version=1),
    )

    assert confirmed.status == SuggestionStatus.approved

    detail = suggestion_service.get_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
    )
    assert detail.quality_signals.runtime_usable is False
    runtime_warnings = detail.quality_signals.runtime_warnings
    assert runtime_warnings


def test_round1_apply_allows_runtime_warning_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    company_id = uuid4()
    actor_user_id = uuid4()
    _patch_access(monkeypatch)
    _wire_generate_from_prompt(
        monkeypatch,
        {
            "Che token noi bo": (
                _draft_heuristic_abstract(),
                _case_meta(has_policy_context=False),
            )
        },
    )

    generated = suggestion_service.generate_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="Che token noi bo"),
    )
    suggestion_service.confirm_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionConfirmIn(reason="ok", expected_version=1),
    )

    fake_rule_id = uuid4()
    monkeypatch.setattr(
        suggestion_service,
        "_apply_rule_draft",
        lambda **_kwargs: SimpleNamespace(id=fake_rule_id, stable_key="personal.custom.manual.office_abstract", name="Office abstract mask", action=RuleAction.mask),
    )
    monkeypatch.setattr(
        suggestion_service,
        "_apply_context_terms",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr(
        suggestion_service,
        "_build_auto_context_terms_from_conditions",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr(
        suggestion_service,
        "_upsert_company_context_terms",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr(
        suggestion_service,
        "_sync_rule_context_term_links",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        suggestion_service,
        "invalidate_context_runtime_cache",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        suggestion_service.RuleEngine,
        "invalidate_cache",
        lambda *args, **kwargs: None,
    )

    applied = suggestion_service.apply_rule_suggestion(
        session=session,  # type: ignore[arg-type]
        company_id=company_id,
        suggestion_id=generated.id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionApplyIn(expected_version=2),
    )

    assert str(applied.rule_id) == str(fake_rule_id)

