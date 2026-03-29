from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.common.error_codes import ErrorCode
from app.common.errors import AppError
from app.suggestion import service as suggestion_service
from app.suggestion.schemas import RuleSuggestionGenerateIn


@pytest.mark.parametrize(
    "prompt",
    [
        "Toi muon chan ma xoxo-oxoxx",
        "Toi muon an ma xxyy-xxyy",
        "An email ca nhan",
        "Chan CCCD",
    ],
)
def test_validate_generate_prompt_intent_allows_single_intent(prompt: str) -> None:
    suggestion_service._validate_generate_prompt_intent(prompt)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "prompt",
    [
        "Toi muon chan ma xoxo-oxoxx va an ma xxyy-xxyy",
        "Toi muon an ma xxyy-xxyy va chan ma xoxo-oxoxx",
        "Chan email abc@gmail.com va an CCCD cua toi",
        "Mask ma ABC-123 va block ma XYZ-999",
        "Chan ma ABC-123 va ma XYZ-999",
    ],
)
def test_validate_generate_prompt_intent_rejects_multi_intent(prompt: str) -> None:
    with pytest.raises(AppError) as exc_info:
        suggestion_service._validate_generate_prompt_intent(prompt)  # type: ignore[attr-defined]

    err = exc_info.value
    assert err.status_code == 422
    assert err.code == ErrorCode.VALIDATION_ERROR
    assert any(
        str(item.get("field") or "") == "prompt"
        and str(item.get("reason") or "") == "multi_intent_prompt_not_supported"
        for item in err.details
    )


def test_generate_rule_suggestion_blocks_multi_intent_before_generate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(suggestion_service, "_load_company_or_404", lambda **kwargs: None)
    monkeypatch.setattr(suggestion_service, "_require_company_admin", lambda **kwargs: None)

    called = {"generate_draft_called": False}

    def _unexpected_generate(**kwargs: object) -> object:
        called["generate_draft_called"] = True
        raise AssertionError("generate draft must not run for multi-intent prompt")

    monkeypatch.setattr(suggestion_service, "_generate_draft_from_prompt", _unexpected_generate)

    with pytest.raises(AppError) as exc_info:
        suggestion_service.generate_rule_suggestion(
            session=SimpleNamespace(),
            company_id=uuid4(),
            actor_user_id=uuid4(),
            payload=RuleSuggestionGenerateIn(
                prompt="Toi muon chan ma xoxo-oxoxx va an ma xxyy-xxyy"
            ),
        )

    err = exc_info.value
    assert err.status_code == 422
    assert err.code == ErrorCode.VALIDATION_ERROR
    assert any(
        str(item.get("reason") or "") == "multi_intent_prompt_not_supported"
        for item in err.details
    )
    assert called["generate_draft_called"] is False
