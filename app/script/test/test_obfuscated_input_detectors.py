from __future__ import annotations

from app.decision.detectors.local_regex_detector import LocalRegexDetector
from app.decision.detectors.obfuscated_email_detector import ObfuscatedEmailDetector
from app.decision.detectors.vn_address_detector import VietnameseAddressDetector


def test_api_secret_detector_matches_openai_live_style_secret() -> None:
    detector = LocalRegexDetector()
    text = "Ban xem giup minh loi nay, minh dang dung key nay: sk_live_abcxyz123456"

    entities = detector.scan(text)

    assert any(str(entity.type) == "API_SECRET" for entity in entities)


def test_api_secret_detector_matches_short_strong_prefix_with_context() -> None:
    detector = LocalRegexDetector()
    text = "Gui key sk-live-ABC123 qua email dev@company.com de debug loi."

    entities = detector.scan(text)

    assert any(
        str(entity.type) == "API_SECRET" and str(entity.text) == "sk-live-ABC123"
        for entity in entities
    )


def test_api_secret_detector_skips_placeholder_secret_example() -> None:
    detector = LocalRegexDetector()
    text = "Trong slide minh viet mau sk-test-xxxxx de minh hoa format key, khong phai secret that."

    entities = detector.scan(text)

    assert not any(str(entity.type) == "API_SECRET" for entity in entities)


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


def test_vn_address_detector_rejects_email_like_prose_fragment() -> None:
    detector = VietnameseAddressDetector()
    text = "Gui key sk-live-ABC123 qua email dev@company.com de debug loi."

    entities = detector.scan(text)

    assert entities == []


def test_vn_address_detector_rejects_generic_city_reference() -> None:
    detector = VietnameseAddressDetector()

    assert detector.scan("Toi song o Ha Noi") == []
    assert detector.scan("Toi o quan Thanh Xuan") == []
    assert detector.scan("Ha Noi rat dep") == []
    assert detector.scan("Nha toi o Ha Noi, gan quan Thanh Xuan") == []


def test_vn_address_detector_detects_house_plus_city() -> None:
    detector = VietnameseAddressDetector()
    text = "Dia chi: So 12 Nguyen Trai, Ha Noi"

    entities = detector.scan(text)

    assert len(entities) == 1
    assert entities[0].type == "ADDRESS"
    assert entities[0].score >= 0.85


def test_vn_address_detector_detects_house_plus_district() -> None:
    detector = VietnameseAddressDetector()
    text = "Nha toi o 45 Le Loi, quan 1"

    entities = detector.scan(text)

    assert len(entities) == 1
    assert entities[0].type == "ADDRESS"
    assert entities[0].score >= 0.85


def test_vn_address_detector_detects_strong_cue_address_without_city_marker() -> None:
    detector = VietnameseAddressDetector()
    text = "So 12, ngo 35 Nguyen Trai, Thanh Xuan"

    entities = detector.scan(text)

    assert len(entities) == 1
    assert entities[0].type == "ADDRESS"
    assert entities[0].score >= 0.85


def test_vn_address_detector_detects_house_street_only() -> None:
    detector = VietnameseAddressDetector()
    text = "Toi o so 12 Nguyen Trai"

    entities = detector.scan(text)

    assert len(entities) == 1
    assert entities[0].type == "ADDRESS"
    assert entities[0].score >= 0.85


def test_local_regex_does_not_detect_token_label_as_api_secret() -> None:
    detector = LocalRegexDetector()
    text = "Trong tai lieu co dong token: abc123"

    entities = detector.scan(text)

    assert not any(str(entity.type) == "API_SECRET" for entity in entities)
