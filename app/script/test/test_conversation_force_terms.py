from __future__ import annotations

from app.conversation import service as conversation_service


def test_force_mask_term_filter_blocks_known_pii_keywords() -> None:
    blocked_terms = [
        "cccd",
        "căn cước",
        "email",
        "phone",
        "số điện thoại",
        "mst",
        "mã số thuế",
        "tax id",
    ]
    for term in blocked_terms:
        assert conversation_service._should_force_mask_term(term) is False  # type: ignore[attr-defined]


def test_force_mask_term_filter_allows_literal_secret_like_terms() -> None:
    allowed_terms = [
        "THUY-XX-YY",
        "ABCD-123",
        "module.auth.v2",
        "dev_key_prod",
        "1234-xxx-zzz",
    ]
    for term in allowed_terms:
        assert conversation_service._should_force_mask_term(term) is True  # type: ignore[attr-defined]
