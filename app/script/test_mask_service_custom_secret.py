from __future__ import annotations

from types import SimpleNamespace

from app.masking.service import MaskService


def test_mask_service_masks_code_like_exact_term_without_entities() -> None:
    service = MaskService()
    text = "Toi co ma don hang zxq-unseen-9981"

    masked = service.mask(
        text,
        entities=[],
        extra_terms=["zxq-unseen-9981"],
    )

    assert masked != text
    assert "zxq-unseen-9981" not in masked.lower()
    assert "[INTERNAL_CODE]" in masked


def test_mask_service_keeps_existing_entity_masking_flow() -> None:
    service = MaskService()
    text = "My email is john@example.com"
    start = text.index("john@example.com")
    end = start + len("john@example.com")
    entity = SimpleNamespace(
        type="EMAIL",
        start=start,
        end=end,
        score=0.99,
        source="local_regex",
    )

    masked = service.mask(text, entities=[entity], extra_terms=None)

    assert masked == "My email is [EMAIL]"


def test_mask_service_does_not_mask_non_code_like_extra_terms() -> None:
    service = MaskService()
    text = "Noi bo hop dong nhan su"

    masked = service.mask(
        text,
        entities=[],
        extra_terms=["hop dong", "nhan su"],
    )

    assert masked == text
