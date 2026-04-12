from __future__ import annotations

from app.suggestion import service as suggestion_service


def test_simulation_detector_adds_spoken_phone_support() -> None:
    text = "So dien thoai cua toi la khong chin bay chin mot hai ba bon nam sau"
    old_entities = suggestion_service._SIMULATE_DETECTOR.scan(text)  # type: ignore[attr-defined]
    new_entities = suggestion_service._detect_simulation_entities(  # type: ignore[attr-defined]
        text=text,
        regex_hints=None,
    )
    assert old_entities == []
    assert any(str(entity.type) == "PHONE" for entity in new_entities)


def test_simulation_detector_adds_spoken_cccd_support() -> None:
    text = "CCCD cua toi la khong bay chin hai khong ba khong khong mot hai ba bon"
    entities = suggestion_service._detect_simulation_entities(  # type: ignore[attr-defined]
        text=text,
        regex_hints=None,
    )
    assert any(str(entity.type) == "CCCD" for entity in entities)


def test_simulation_detector_adds_spoken_tax_id_support_with_tax_context() -> None:
    text = "Ma so thue cua toi la khong mot khong mot hai ba bon nam sau bay"
    entities = suggestion_service._detect_simulation_entities(  # type: ignore[attr-defined]
        text=text,
        regex_hints=None,
    )
    assert any(str(entity.type) == "TAX_ID" for entity in entities)
