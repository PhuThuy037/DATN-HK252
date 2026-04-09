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


def test_mask_service_does_not_remask_inside_existing_placeholders() -> None:
    service = MaskService()
    text = "CCCD cua toi la [CCCD]"

    masked = service.mask(
        text,
        entities=[],
        force_terms=["cccd"],
    )

    assert "[[INTERNAL_CODE]]" not in masked
    assert "[CCCD]" in masked


def test_mask_service_masks_address_entities() -> None:
    service = MaskService()
    text = "Dia chi cua toi la 268 Ly Thuong Kiet, phuong 14, quan 10, TP.HCM"
    start = text.index("268 Ly Thuong Kiet")
    end = len(text)
    entity = SimpleNamespace(
        type="ADDRESS",
        start=start,
        end=end,
        score=0.91,
        source="vn_address",
    )

    masked = service.mask(text, entities=[entity], extra_terms=None)

    assert masked == "Dia chi cua toi la [ADDRESS]"


def test_mask_service_prefers_api_secret_over_nested_phone() -> None:
    service = MaskService()
    text = "Key la sk_live_51abcXYZ09876543210"
    secret_start = text.index("sk_live_51abcXYZ09876543210")
    secret_end = len(text)
    phone_start = text.index("09876543210")
    phone_end = phone_start + len("09876543210")

    masked = service.mask(
        text,
        entities=[
            SimpleNamespace(
                type="PHONE",
                start=phone_start,
                end=phone_end,
                score=0.90,
                source="local_regex",
            ),
            SimpleNamespace(
                type="API_SECRET",
                start=secret_start,
                end=secret_end,
                score=0.98,
                source="local_regex",
            ),
        ],
        extra_terms=None,
    )

    assert masked == "Key la [API_SECRET]"
