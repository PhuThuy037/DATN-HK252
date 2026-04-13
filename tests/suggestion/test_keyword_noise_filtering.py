from __future__ import annotations

import unicodedata

from app.suggestion import suggestion_postprocess


def _fold_text(value: str) -> str:
    raw = str(value or "").lower().replace("\u0111", "d")
    normalized = unicodedata.normalize("NFKD", raw)
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(no_marks.split())


class _FakeService:
    @staticmethod
    def _fold_text(value: str) -> str:
        return _fold_text(value)

    @staticmethod
    def _contains_prompt_keyword(*, folded_prompt: str, keyword: str) -> bool:
        return keyword in folded_prompt

    @staticmethod
    def _normalize_phrase_text(value: str) -> str:
        text = " ".join(str(value or "").strip().lower().split())
        return text.strip(" \t\r\n,.;:!?\"'()[]{}")

    @staticmethod
    def _extract_target_phrases(prompt: str, *, limit: int = 4) -> list[str]:
        _ = limit
        folded = _fold_text(prompt)
        targets = [
            "phong k",
            "phong t",
            "trung tam m",
            "trung tam y",
            "cong ty z",
            "bo phan x",
            "nhan vien b",
        ]
        return [target for target in targets if target in folded]


def _install_fake_service(monkeypatch) -> None:
    monkeypatch.setattr(suggestion_postprocess, "_svc", lambda: _FakeService())


def test_sanitize_context_keyword_values_keeps_phrase_for_phong_k(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_keyword_values(
        ["thông tin về Phòng K"],
        fallback_phrases=["thông tin về Phòng K"],
    )
    assert result == ["thông tin về phòng k"]


def test_sanitize_context_keyword_values_keeps_phrase_for_trung_tam_m(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_keyword_values(
        ["tài liệu nội bộ của Trung tâm M"],
        fallback_phrases=["tài liệu nội bộ của Trung tâm M"],
    )
    assert result == ["tài liệu nội bộ của trung tâm m"]


def test_sanitize_context_keyword_values_keeps_phrase_for_cong_ty_z(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_keyword_values(
        ["các nội dung về Công ty Z"],
        fallback_phrases=["các nội dung về Công ty Z"],
    )
    assert result == ["các nội dung về công ty z"]


def test_sanitize_context_keyword_values_drops_connector_only_noise(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_keyword_values(
        ["bộ của", "liên quan đến"],
        fallback_phrases=["phong k"],
    )
    assert result == ["phong k"]


def test_sanitize_context_keyword_values_keeps_trung_tam_y(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_keyword_values(
        ["trung tam y"],
        fallback_phrases=["trung tam y"],
    )
    assert result == ["trung tam y"]


def test_sanitize_context_keyword_values_keeps_nhan_vien_b(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_keyword_values(
        ["nhan vien b"],
        fallback_phrases=["nhan vien b"],
    )
    assert result == ["nhan vien b"]
