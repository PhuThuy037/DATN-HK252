from __future__ import annotations

from app.decision.context_scorer import ContextScorer


def test_persona_keyword_overrides_extend_defaults_instead_of_replacing() -> None:
    scorer = ContextScorer("app/config/context_base.yaml")
    text = "Ban giup minh debug loi API nay voi, dang goi endpoint bi 401"

    ctx = scorer.score(
        text,
        persona_keywords_override={
            "dev": [".env", "token"],
        },
    )

    assert ctx.persona == "dev"
    assert "debug" in ctx.keyword_hits
    assert "api" in ctx.keyword_hits
    assert "401" in ctx.keyword_hits
