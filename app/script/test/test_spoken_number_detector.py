from __future__ import annotations

from app.decision.detectors.spoken_number_detector import SpokenNumberDetector


def _top_type(text: str) -> str | None:
    detector = SpokenNumberDetector()
    entities = detector.scan(text)
    if not entities:
        return None
    entities.sort(key=lambda e: float(getattr(e, "score", 0.0)), reverse=True)
    return str(entities[0].type)


def test_spoken_phone_detected() -> None:
    text = "So dien thoai cua toi la khong chin bay chin mot hai ba bon nam sau"
    assert _top_type(text) == "PHONE"


def test_spoken_cccd_detected() -> None:
    text = "CCCD cua toi la khong bay chin hai khong ba khong khong mot hai ba bon"
    assert _top_type(text) == "CCCD"


def test_spoken_tax_id_requires_tax_context_and_passes_with_context() -> None:
    text = "Ma so thue cua toi la khong mot khong mot hai ba bon nam sau bay"
    assert _top_type(text) == "TAX_ID"


def test_spoken_tax_id_not_classified_for_non_tax_context() -> None:
    detector = SpokenNumberDetector()
    text = "Ma don hang cua toi la khong mot khong mot hai ba bon nam sau bay"
    entities = detector.scan(text)
    assert all(str(entity.type) != "TAX_ID" for entity in entities)
