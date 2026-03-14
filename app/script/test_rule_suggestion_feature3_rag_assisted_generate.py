from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity
from app.suggestion import service as suggestion_service
from app.suggestion.schemas import (
    DuplicateDecision,
    RuleDuplicateCheckOut,
    RuleSuggestionDraftContextTerm,
    RuleSuggestionDraftPayload,
    RuleSuggestionDraftRule,
    RuleSuggestionGenerateIn,
    RuleSuggestionOut,
    SuggestionStatus,
)


def _sample_draft(*, stable_key: str = "company.custom.rag.feature3") -> RuleSuggestionDraftPayload:
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key=stable_key,
            name="Feature3 RAG Generate",
            description="draft for rag-assisted generation tests",
            scope=RuleScope.prompt,
            conditions={"any": [{"entity_type": "EMAIL"}]},
            action=RuleAction.mask,
            severity=RuleSeverity.medium,
            priority=50,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[],
    )


def _duplicate_check() -> RuleDuplicateCheckOut:
    return RuleDuplicateCheckOut(
        decision=DuplicateDecision.different,
        confidence=0.9,
        rationale="unit_test",
        matched_rule_ids=[],
        candidates=[],
        top_k=5,
        exact_threshold=0.95,
        near_threshold=0.8,
        source="unit_test",
        llm_provider=None,
        llm_model=None,
        llm_fallback_used=False,
    )


def _out_payload(*, company_id: UUID, actor_user_id: UUID, draft: RuleSuggestionDraftPayload) -> RuleSuggestionOut:
    now = datetime.now(timezone.utc)
    return RuleSuggestionOut(
        id=uuid4(),
        rule_set_id=company_id,
        created_by=actor_user_id,
        status=SuggestionStatus.draft,
        type="rule_with_context",
        version=1,
        nl_input="test prompt",
        dedupe_key="dedupe_key_test",
        draft=draft,
        applied_result_json=None,
        expires_at=None,
        created_at=now,
        updated_at=now,
    )


class _FakeSession:
    def add(self, _row: object) -> None:
        return None

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def refresh(self, _row: object) -> None:
        return None


def test_feature3_generate_uses_retrieval_context_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    company_id = uuid4()
    actor_user_id = uuid4()

    class _FakeRetriever:
        def __init__(self, *, session: object, company_id: UUID) -> None:
            self.session = session
            self.company_id = company_id

        def retrieve_policy_chunks(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return [
                {"chunk_id": "p_12", "content": "mask personal email", "similarity": 0.91}
            ]

        def retrieve_related_rules(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return [{"rule_id": "r_101", "stable_key": "company.custom.existing"}]

    def _fake_generate_with_llm(
        prompt: str,
        *,
        prompt_keywords: list[str],
        policy_chunks: list[dict[str, object]],
        rule_references: list[dict[str, object]],
    ) -> tuple[RuleSuggestionDraftPayload, dict[str, object]]:
        captured["prompt"] = prompt
        captured["prompt_keywords"] = list(prompt_keywords)
        captured["policy_chunks"] = list(policy_chunks)
        captured["rule_references"] = list(rule_references)
        return _sample_draft(), {
            "source": "llm",
            "provider": "mock",
            "model": "mock-model",
            "fallback_used": False,
        }

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(suggestion_service, "_generate_with_llm", _fake_generate_with_llm)

    draft, meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=company_id,
        actor_user_id=actor_user_id,
        prompt="Please mask partner email data",
    )

    assert isinstance(draft, RuleSuggestionDraftPayload)
    assert captured["policy_chunks"] == [
        {"chunk_id": "p_12", "content": "mask personal email", "similarity": 0.91}
    ]
    assert captured["rule_references"] == [{"rule_id": "r_101", "stable_key": "company.custom.existing"}]
    assert meta["context_retrieval"]["has_policy_context"] is True
    assert meta["context_retrieval"]["policy_chunk_ids"] == ["p_12"]
    assert meta["context_retrieval"]["related_rule_ids"] == ["r_101"]


def test_feature3_generate_response_has_retrieval_context_shape_and_policy_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = uuid4()
    actor_user_id = uuid4()
    draft = _sample_draft()
    out_payload = _out_payload(company_id=company_id, actor_user_id=actor_user_id, draft=draft)

    generation_meta = {
        "source": "llm",
        "provider": "mock",
        "model": "mock-model",
        "fallback_used": False,
        "context_retrieval": {
            "has_policy_context": True,
            "policy_chunk_ids": ["p_12", "p_19"],
            "related_rule_ids": ["r_101", "r_102"],
            "policy_chunks": 2,
            "related_rules": 2,
        },
    }

    monkeypatch.setattr(suggestion_service, "_load_company_or_404", lambda **kwargs: None)
    monkeypatch.setattr(suggestion_service, "_require_company_admin", lambda **kwargs: None)
    monkeypatch.setattr(
        suggestion_service,
        "_generate_draft_from_prompt",
        lambda **kwargs: (draft, generation_meta),
    )
    monkeypatch.setattr(suggestion_service, "build_duplicate_check", lambda **kwargs: _duplicate_check())
    monkeypatch.setattr(suggestion_service, "_dedupe_key", lambda **kwargs: "dedupe_unit")
    monkeypatch.setattr(suggestion_service, "_find_active_duplicate", lambda **kwargs: None)
    monkeypatch.setattr(suggestion_service, "_append_log", lambda **kwargs: None)
    monkeypatch.setattr(suggestion_service, "_to_out", lambda _row: out_payload)
    monkeypatch.setattr(suggestion_service, "_snapshot_suggestion", lambda _row: {})
    monkeypatch.setattr(
        suggestion_service,
        "RuleSuggestion",
        lambda **kwargs: SimpleNamespace(id=uuid4(), **kwargs),
    )

    result = suggestion_service.generate_rule_suggestion(
        session=_FakeSession(),
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="Generate masking rule"),
    )

    ctx = result.retrieval_context.model_dump()
    assert set(ctx.keys()) == {"has_policy_context", "policy_chunk_ids", "related_rule_ids"}
    assert ctx["policy_chunk_ids"] == ["p_12", "p_19"]
    assert ctx["related_rule_ids"] == ["r_101", "r_102"]
    assert ctx["has_policy_context"] is True
    assert result.quality_signals.has_policy_context is True


def test_feature3_generate_draft_handles_empty_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRetriever:
        def __init__(self, *, session: object, company_id: UUID) -> None:
            self.session = session
            self.company_id = company_id

        def retrieve_policy_chunks(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return []

        def retrieve_related_rules(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return []

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(
        suggestion_service,
        "_generate_with_llm",
        lambda *_args, **_kwargs: (
            _sample_draft(),
            {"source": "llm", "provider": "mock", "model": "mock-model", "fallback_used": False},
        ),
    )

    draft, meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt="Mask email addresses",
    )

    assert isinstance(draft, RuleSuggestionDraftPayload)
    assert meta["context_retrieval"]["has_policy_context"] is False
    assert meta["context_retrieval"]["policy_chunk_ids"] == []
    assert meta["context_retrieval"]["related_rule_ids"] == []


def test_feature3_generate_draft_handles_retrieval_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _never_used_retrieve(**_kwargs: object) -> list[object]:
        return []

    def _fake_init(self: object, *, session: object, company_id: UUID) -> None:
        self.session = session
        self.company_id = company_id
        self.policy_retriever = SimpleNamespace(retrieve=_never_used_retrieve)

    monkeypatch.setattr(suggestion_service.SuggestionContextRetriever, "__init__", _fake_init)
    monkeypatch.setattr(
        suggestion_service,
        "_run_coro_sync",
        lambda _coro: (_ for _ in ()).throw(RuntimeError("policy_retriever_failed")),
    )
    monkeypatch.setattr(
        suggestion_service,
        "_build_rule_references",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("rule_reference_failed")),
    )
    monkeypatch.setattr(
        suggestion_service,
        "_generate_with_llm",
        lambda *_args, **_kwargs: (
            _sample_draft(),
            {"source": "llm", "provider": "mock", "model": "mock-model", "fallback_used": False},
        ),
    )

    draft, meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt="Block payroll leaks",
    )

    assert isinstance(draft, RuleSuggestionDraftPayload)
    assert meta["context_retrieval"]["has_policy_context"] is False
    assert meta["context_retrieval"]["policy_chunk_ids"] == []
    assert meta["context_retrieval"]["related_rule_ids"] == []


def test_feature3_fallback_heuristic_still_works_with_retrieval_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeRetriever:
        def __init__(self, *, session: object, company_id: UUID) -> None:
            self.session = session
            self.company_id = company_id

        def retrieve_policy_chunks(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return [{"chunk_id": "p_77", "content": "block payroll sharing", "similarity": 0.9}]

        def retrieve_related_rules(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return [{"rule_id": "r_777", "stable_key": "company.custom.payroll.guard"}]

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(
        suggestion_service,
        "_generate_with_llm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("llm_failed")),
    )

    draft, meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt="Block payroll data to external email",
    )

    assert isinstance(draft, RuleSuggestionDraftPayload)
    assert str(meta.get("source")) == "fallback_generator"
    assert meta["context_retrieval"]["policy_chunk_ids"] == ["p_77"]
    assert meta["context_retrieval"]["related_rule_ids"] == ["r_777"]


def test_feature3_generate_draft_keeps_normalize_and_semantic_guard_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class _FakeRetriever:
        def __init__(self, *, session: object, company_id: UUID) -> None:
            self.session = session
            self.company_id = company_id

        def retrieve_policy_chunks(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return [{"chunk_id": "p_90", "content": "sample policy", "similarity": 0.8}]

        def retrieve_related_rules(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return [{"rule_id": "r_900", "stable_key": "company.custom.sample"}]

    def _ensure(*, prompt: str, draft: RuleSuggestionDraftPayload) -> RuleSuggestionDraftPayload:
        _ = prompt
        calls.append("ensure")
        return draft.model_copy(
            update={
                "rule": draft.rule.model_copy(
                    update={"stable_key": "company.custom.after.ensure"}
                )
            }
        )

    def _align(prompt: str, draft: RuleSuggestionDraftPayload) -> RuleSuggestionDraftPayload:
        _ = prompt
        calls.append("align")
        return draft

    def _semantic(prompt: str, draft: RuleSuggestionDraftPayload) -> RuleSuggestionDraftPayload:
        _ = prompt
        calls.append("semantic_guard")
        return draft

    def _normalize(draft: RuleSuggestionDraftPayload) -> RuleSuggestionDraftPayload:
        calls.append("normalize")
        return draft

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _FakeRetriever)
    monkeypatch.setattr(
        suggestion_service,
        "_generate_with_llm",
        lambda *_args, **_kwargs: (
            _sample_draft(stable_key="temporary.bad.key"),
            {"source": "llm", "provider": "mock", "model": "mock-model", "fallback_used": False},
        ),
    )
    monkeypatch.setattr(suggestion_service, "_ensure_company_stable_key", _ensure)
    monkeypatch.setattr(suggestion_service, "_align_draft_with_prompt", _align)
    monkeypatch.setattr(suggestion_service, "_enforce_prompt_semantic_guard", _semantic)
    monkeypatch.setattr(suggestion_service, "_normalize_draft", _normalize)

    draft, meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt="Mask candidate email",
    )

    assert calls == ["ensure", "align", "semantic_guard", "normalize"]
    assert draft.rule.stable_key == "company.custom.after.ensure"
    assert meta["context_retrieval"]["policy_chunk_ids"] == ["p_90"]
    assert meta["context_retrieval"]["related_rule_ids"] == ["r_900"]


def test_feature3_generate_keeps_duplicate_check_flow_after_retrieval_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = uuid4()
    actor_user_id = uuid4()
    draft = _sample_draft(stable_key="company.custom.dup.check")
    out_payload = _out_payload(company_id=company_id, actor_user_id=actor_user_id, draft=draft)
    duplicate_check = _duplicate_check()
    captured: dict[str, object] = {}

    generation_meta = {
        "source": "llm",
        "provider": "mock",
        "model": "mock-model",
        "fallback_used": False,
        "context_retrieval": {
            "has_policy_context": True,
            "policy_chunk_ids": ["p_44"],
            "related_rule_ids": ["r_44"],
            "policy_chunks": 1,
            "related_rules": 1,
        },
    }

    def _capture_duplicate_check(**kwargs: object) -> RuleDuplicateCheckOut:
        captured["draft_rule"] = kwargs.get("draft_rule")
        captured["company_id"] = kwargs.get("company_id")
        return duplicate_check

    monkeypatch.setattr(suggestion_service, "_load_company_or_404", lambda **kwargs: None)
    monkeypatch.setattr(suggestion_service, "_require_company_admin", lambda **kwargs: None)
    monkeypatch.setattr(
        suggestion_service,
        "_generate_draft_from_prompt",
        lambda **kwargs: (draft, generation_meta),
    )
    monkeypatch.setattr(suggestion_service, "build_duplicate_check", _capture_duplicate_check)
    monkeypatch.setattr(suggestion_service, "_dedupe_key", lambda **kwargs: "dedupe_unit")
    monkeypatch.setattr(
        suggestion_service,
        "_find_active_duplicate",
        lambda **kwargs: SimpleNamespace(id=uuid4()),
    )
    monkeypatch.setattr(suggestion_service, "_append_log", lambda **kwargs: None)
    monkeypatch.setattr(suggestion_service, "_snapshot_suggestion", lambda _row: {})
    monkeypatch.setattr(suggestion_service, "_to_out", lambda _row: out_payload)

    result = suggestion_service.generate_rule_suggestion(
        session=_FakeSession(),
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="generate duplicate check flow"),
    )

    assert captured["company_id"] == company_id
    assert captured["draft_rule"] == draft.rule
    assert result.duplicate_check.decision == duplicate_check.decision
    assert result.retrieval_context.policy_chunk_ids == ["p_44"]


def test_feature3_custom_secret_prompt_prioritizes_exact_term_not_generic_pii() -> None:
    prompt = "Tạo rule mask mã nội bộ ZXQ-UNSEEN-9981"
    draft = suggestion_service._fallback_generate(prompt)  # type: ignore[attr-defined]
    conditions = draft.rule.conditions

    assert draft.rule.action == RuleAction.mask
    assert suggestion_service._contains_entity_type(  # type: ignore[attr-defined]
        conditions, {"PHONE", "CCCD", "TAX_ID", "EMAIL", "CREDIT_CARD"}
    ) is False
    terms = {str(t.term).lower() for t in draft.context_terms}
    assert "zxq-unseen-9981" in terms


def test_feature3_payroll_external_email_prompt_not_generic_office_branch() -> None:
    prompt = "Tạo rule block gửi danh sách lương payroll ra email cá nhân như gmail"
    draft = suggestion_service._fallback_generate(prompt)  # type: ignore[attr-defined]
    cond = draft.rule.conditions

    assert draft.rule.action == RuleAction.block
    assert suggestion_service._condition_has_context_keyword_term(  # type: ignore[attr-defined]
        cond, "payroll"
    )
    assert suggestion_service._condition_has_context_keyword_term(  # type: ignore[attr-defined]
        cond, "gmail"
    )
    assert "office context" not in str(draft.rule.name).lower()


def test_feature3_align_guard_rewrites_bad_llm_mapping_for_custom_secret() -> None:
    prompt = "Che token nội bộ ALPHA-SECRET-2026"
    llm_bad = _sample_draft(stable_key="company.custom.bad.map")

    # Simulate wrong LLM map to common PII.
    llm_bad = llm_bad.model_copy(
        update={
            "rule": llm_bad.rule.model_copy(
                update={
                    "conditions": {
                        "any": [
                            {"entity_type": "PHONE"},
                            {"entity_type": "EMAIL"},
                        ]
                    }
                }
            )
        }
    )

    aligned = suggestion_service._align_draft_with_prompt(  # type: ignore[attr-defined]
        prompt,
        llm_bad,
    )
    guarded = suggestion_service._enforce_prompt_semantic_guard(  # type: ignore[attr-defined]
        prompt,
        aligned,
    )

    assert suggestion_service._contains_entity_type(  # type: ignore[attr-defined]
        guarded.rule.conditions, {"PHONE", "EMAIL", "CCCD", "TAX_ID", "CREDIT_CARD"}
    ) is False
    assert suggestion_service._draft_has_exact_secret_terms(  # type: ignore[attr-defined]
        guarded,
        ["ALPHA-SECRET-2026"],
    )


def test_feature3_post_generate_intent_guard_sets_meta_and_quality_flags() -> None:
    prompt = "Block chuoi bi mat PRJ-X-7788"
    llm_bad = _sample_draft(stable_key="company.custom.bad.guard").model_copy(
        update={
            "rule": _sample_draft().rule.model_copy(
                update={"conditions": {"any": [{"entity_type": "EMAIL"}]}}
            )
        }
    )

    repaired, guard_meta = suggestion_service._post_generate_intent_guard(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=llm_bad,
    )

    assert guard_meta["applied"] is True
    assert guard_meta["mismatch_detected"] is True
    quality = suggestion_service._build_quality_signals(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=repaired,
        duplicate_meta={"decision": "DIFFERENT", "confidence": 0.92},
        generation_meta={"source": "llm", "intent_guard": guard_meta},
    )
    assert quality.intent_guard_applied is True
    assert quality.intent_mismatch_detected is True


def test_feature3_office_prompt_guard_removes_leaked_token_and_quality_warns() -> None:
    prompt = "Tạo rule mask thông tin hợp đồng nội bộ trong ngữ cảnh office"
    bad = _sample_draft(stable_key="company.custom.bad.office.leak").model_copy(
        update={
            "rule": _sample_draft().rule.model_copy(
                update={
                    "conditions": {
                        "all": [
                            {
                                "signal": {
                                    "field": "context_keywords",
                                    "any_of": ["exact", "token", "zxq-unseen-9981"],
                                }
                            }
                        ]
                    }
                }
            ),
            "context_terms": [
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
        }
    )

    guarded, guard_meta = suggestion_service._post_generate_intent_guard(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=bad,
    )

    assert guard_meta["applied"] is True
    assert guard_meta["mismatch_detected"] is True
    assert "removed_unprompted_code_like_terms" in guard_meta["reasons"]
    assert suggestion_service._condition_has_context_keyword_term(  # type: ignore[attr-defined]
        guarded.rule.conditions,
        "zxq-unseen-9981",
    ) is False
    assert all(str(t.term).lower() != "zxq-unseen-9981" for t in guarded.context_terms)

    explanation = suggestion_service._build_suggestion_explanation(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=guarded,
        duplicate_meta={"decision": "DIFFERENT", "confidence": 0.9},
    )
    assert "zxq-unseen-9981" not in {str(x).lower() for x in explanation.derived_terms}

    quality = suggestion_service._build_quality_signals(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=guarded,
        duplicate_meta={"decision": "DIFFERENT", "confidence": 0.9},
        generation_meta={"source": "llm", "intent_guard": guard_meta},
    )
    assert quality.runtime_usable is False
    assert "abstract_context_keywords_not_runtime_usable" in quality.runtime_warnings


def test_feature3_runtime_usability_flags_unprompted_code_anchor() -> None:
    prompt = "Tạo rule mask thông tin hợp đồng nội bộ trong ngữ cảnh office"
    bad = _sample_draft(stable_key="company.custom.bad.unprompted.anchor").model_copy(
        update={
            "rule": _sample_draft().rule.model_copy(
                update={
                    "conditions": {
                        "all": [
                            {
                                "signal": {
                                    "field": "context_keywords",
                                    "any_of": ["zxq-unseen-9981"],
                                }
                            }
                        ]
                    }
                }
            ),
            "context_terms": [
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
        }
    )

    quality = suggestion_service._build_quality_signals(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=bad,
        duplicate_meta={"decision": "DIFFERENT", "confidence": 0.9},
        generation_meta={"source": "llm"},
    )
    assert quality.runtime_usable is False
    assert "unexpected_code_like_term_not_in_prompt" in quality.runtime_warnings


def test_feature3_quality_confidence_penalized_when_mismatch_unrepaired() -> None:
    prompt = "Che token noi bo ALPHA-SECRET-2026"
    draft = _sample_draft()
    duplicate_meta = {"decision": "DIFFERENT", "confidence": 0.95}

    quality_base = suggestion_service._build_quality_signals(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=draft,
        duplicate_meta=duplicate_meta,
        generation_meta={"source": "llm"},
    )
    quality_mismatch = suggestion_service._build_quality_signals(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=draft,
        duplicate_meta=duplicate_meta,
        generation_meta={
            "source": "llm",
            "intent_guard": {"applied": False, "mismatch_detected": True},
        },
    )

    assert quality_mismatch.intent_mismatch_detected is True
    assert quality_mismatch.intent_guard_applied is False
    assert quality_mismatch.intent_confidence < quality_base.intent_confidence


def test_feature3_custom_secret_guard_repairs_abstract_keyword_condition() -> None:
    prompt = "Tao rule mask ma noi bo ZXQ-UNSEEN-9981"
    bad = _sample_draft(stable_key="company.custom.abstract.keyword").model_copy(
        update={
            "rule": _sample_draft().rule.model_copy(
                update={
                    "conditions": {
                        "all": [
                            {
                                "signal": {
                                    "field": "context_keywords",
                                    "any_of": ["exact", "token"],
                                }
                            }
                        ]
                    }
                }
            ),
            "context_terms": [
                {
                    "entity_type": "INTERNAL_CODE",
                    "term": "zxq-unseen-9981",
                    "lang": "vi",
                    "weight": 1.0,
                    "window_1": 60,
                    "window_2": 20,
                    "enabled": True,
                }
            ],
        }
    )

    guarded, meta = suggestion_service._post_generate_intent_guard(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=bad,
    )

    assert meta["applied"] is True
    assert meta["mismatch_detected"] is True
    assert suggestion_service._condition_has_context_keyword_term(  # type: ignore[attr-defined]
        guarded.rule.conditions,
        "zxq-unseen-9981",
    )


def test_feature3_generate_flow_custom_secret_guard_repairs_bad_llm_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _EmptyRetriever:
        def __init__(self, *, session: object, company_id: UUID) -> None:
            self.session = session
            self.company_id = company_id

        def retrieve_policy_chunks(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return []

        def retrieve_related_rules(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return []

    bad_llm = _sample_draft(stable_key="company.custom.bad.customsecret").model_copy(
        update={
            "rule": _sample_draft().rule.model_copy(
                update={"conditions": {"any": [{"entity_type": "PHONE"}]}}
            )
        }
    )

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _EmptyRetriever)
    monkeypatch.setattr(
        suggestion_service,
        "_generate_with_llm",
        lambda *_args, **_kwargs: (
            bad_llm,
            {"source": "llm", "provider": "mock", "model": "mock-model", "fallback_used": False},
        ),
    )
    monkeypatch.setattr(suggestion_service, "_align_draft_with_prompt", lambda _p, d: d)
    monkeypatch.setattr(suggestion_service, "_enforce_prompt_semantic_guard", lambda _p, d: d)

    prompt = "Tao rule mask ma noi bo ZXQ-UNSEEN-9981"
    draft, meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt=prompt,
    )

    assert suggestion_service._contains_entity_type(  # type: ignore[attr-defined]
        draft.rule.conditions, {"PHONE", "CCCD", "TAX_ID", "EMAIL", "CREDIT_CARD"}
    ) is False
    assert suggestion_service._draft_has_exact_secret_terms(  # type: ignore[attr-defined]
        draft,
        ["ZXQ-UNSEEN-9981"],
    )
    assert meta["intent_guard"]["applied"] is True
    assert meta["intent_guard"]["mismatch_detected"] is True


def test_feature3_generate_flow_payroll_external_guard_repairs_generic_office_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _EmptyRetriever:
        def __init__(self, *, session: object, company_id: UUID) -> None:
            self.session = session
            self.company_id = company_id

        def retrieve_policy_chunks(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return []

        def retrieve_related_rules(
            self,
            prompt: str,
            user_id: UUID,
            top_k: int = 3,
        ) -> list[dict[str, object]]:
            _ = (prompt, user_id, top_k)
            return []

    bad_llm = _sample_draft(stable_key="company.custom.bad.payroll").model_copy(
        update={
            "rule": _sample_draft().rule.model_copy(
                update={
                    "name": "Suggested office context block",
                    "action": RuleAction.block,
                    "conditions": {"all": [{"signal": {"field": "persona", "equals": "office"}}]},
                }
            )
        }
    )

    monkeypatch.setattr(suggestion_service, "SuggestionContextRetriever", _EmptyRetriever)
    monkeypatch.setattr(
        suggestion_service,
        "_generate_with_llm",
        lambda *_args, **_kwargs: (
            bad_llm,
            {"source": "llm", "provider": "mock", "model": "mock-model", "fallback_used": False},
        ),
    )
    monkeypatch.setattr(suggestion_service, "_align_draft_with_prompt", lambda _p, d: d)
    monkeypatch.setattr(suggestion_service, "_enforce_prompt_semantic_guard", lambda _p, d: d)

    prompt = "Tao rule block gui danh sach luong payroll ra email ca nhan nhu gmail"
    draft, meta = suggestion_service._generate_draft_from_prompt(  # type: ignore[attr-defined]
        session=SimpleNamespace(),
        company_id=uuid4(),
        actor_user_id=uuid4(),
        prompt=prompt,
    )

    assert suggestion_service._condition_has_context_keyword_term(  # type: ignore[attr-defined]
        draft.rule.conditions, "payroll"
    )
    assert suggestion_service._condition_has_context_keyword_term(  # type: ignore[attr-defined]
        draft.rule.conditions, "gmail"
    )
    assert "office context" not in str(draft.rule.name).lower()
    assert meta["intent_guard"]["applied"] is True
    assert meta["intent_guard"]["mismatch_detected"] is True


def test_feature3_post_generate_intent_guard_noop_for_non_target_prompt() -> None:
    prompt = "Mask phone numbers in normal customer support chats"
    original = _sample_draft(stable_key="company.custom.keep.as.is")

    guarded, guard_meta = suggestion_service._post_generate_intent_guard(  # type: ignore[attr-defined]
        prompt=prompt,
        draft=original,
    )

    assert guard_meta["applied"] is False
    assert guard_meta["mismatch_detected"] is False
    assert guarded.model_dump() == original.model_dump()


def test_feature3_backward_compat_generate_contract_intact_for_regular_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company_id = uuid4()
    actor_user_id = uuid4()
    draft = _sample_draft(stable_key="company.custom.regular.prompt")
    out_payload = _out_payload(company_id=company_id, actor_user_id=actor_user_id, draft=draft)

    generation_meta = {
        "source": "llm",
        "provider": "mock",
        "model": "mock-model",
        "fallback_used": False,
        "context_retrieval": {
            "has_policy_context": False,
            "policy_chunk_ids": [],
            "related_rule_ids": [],
            "policy_chunks": 0,
            "related_rules": 0,
        },
        "intent_guard": {"applied": False, "mismatch_detected": False},
    }

    monkeypatch.setattr(suggestion_service, "_load_company_or_404", lambda **kwargs: None)
    monkeypatch.setattr(suggestion_service, "_require_company_admin", lambda **kwargs: None)
    monkeypatch.setattr(
        suggestion_service,
        "_generate_draft_from_prompt",
        lambda **kwargs: (draft, generation_meta),
    )
    monkeypatch.setattr(suggestion_service, "build_duplicate_check", lambda **kwargs: _duplicate_check())
    monkeypatch.setattr(suggestion_service, "_dedupe_key", lambda **kwargs: "dedupe_regular")
    monkeypatch.setattr(suggestion_service, "_find_active_duplicate", lambda **kwargs: None)
    monkeypatch.setattr(suggestion_service, "_append_log", lambda **kwargs: None)
    monkeypatch.setattr(suggestion_service, "_to_out", lambda _row: out_payload)
    monkeypatch.setattr(suggestion_service, "_snapshot_suggestion", lambda _row: {})
    monkeypatch.setattr(
        suggestion_service,
        "RuleSuggestion",
        lambda **kwargs: SimpleNamespace(id=uuid4(), **kwargs),
    )

    result = suggestion_service.generate_rule_suggestion(
        session=_FakeSession(),
        company_id=company_id,
        actor_user_id=actor_user_id,
        payload=RuleSuggestionGenerateIn(prompt="Mask customer contact details"),
    )

    assert result.id == out_payload.id
    assert result.status == out_payload.status
    assert result.draft == out_payload.draft
    assert result.duplicate_check.decision == DuplicateDecision.different
    assert isinstance(result.explanation.summary, str) and result.explanation.summary
    assert result.quality_signals.intent_guard_applied is False
    assert result.quality_signals.intent_mismatch_detected is False
    assert result.retrieval_context.has_policy_context is False
    assert result.retrieval_context.policy_chunk_ids == []
