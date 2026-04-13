from __future__ import annotations

from app.decision.detectors.local_regex_detector import LocalRegexDetector
from app.decision.detectors.obfuscated_email_detector import ObfuscatedEmailDetector
from app.decision.detectors.vn_address_detector import VietnameseAddressDetector


def test_api_secret_detector_matches_openai_live_style_secret() -> None:
    detector = LocalRegexDetector()
    text = "Ban xem giup minh loi nay, minh dang dung key nay: sk_live_abcxyz123456"

    entities = detector.scan(text)

    assert any(str(entity.type) == "API_SECRET" for entity in entities)


def test_obfuscated_email_detector_detects_spoken_email() -> None:
    detector = ObfuscatedEmailDetector()
    text = (
        "Ban sua lai cau nay: mail cua minh la "
        "thuy dev demo a cong gmail cham com cho dung format"
    )

    entities = detector.scan(text)

    assert len(entities) == 1
    entity = entities[0]
    assert entity.type == "EMAIL"
    assert entity.score >= 0.80
    assert entity.metadata["normalized"] == "thuydevdemo@gmail.com"


def test_vn_address_detector_detects_structured_address() -> None:
    detector = VietnameseAddressDetector()
    text = (
        "Ban chuan hoa giup minh dia chi nay: "
        "268 Ly Thuong Kiet, phuong 14, quan 10, TP.HCM"
    )

    entities = detector.scan(text)

    assert len(entities) == 1
    entity = entities[0]
    assert entity.type == "ADDRESS"
    assert entity.score >= 0.85


def test_vn_address_detector_does_not_match_password_field_line() -> None:
    detector = VietnameseAddressDetector()
    text = "password: 123456"

    entities = detector.scan(text)

    assert entities == []


def test_vn_address_detector_does_not_match_password_field_with_multiline_prose() -> None:
    detector = VietnameseAddressDetector()
    text = "password: 123456\n\nAnh xem giup em roi phan hoi som nhe"

    entities = detector.scan(text)

    assert entities == []


def test_local_regex_does_not_detect_token_label_as_api_secret() -> None:
    detector = LocalRegexDetector()
    text = "Trong tai lieu co dong token: abc123"

    entities = detector.scan(text)

    assert not any(str(entity.type) == "API_SECRET" for entity in entities)
