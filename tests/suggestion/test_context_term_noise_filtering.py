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
            "truong nhom q",
            "trung tam m",
            "trung tam y",
            "cong ty z",
            "bo phan x",
            "du an c",
            "nhan vien b",
            "phong r",
        ]
        return [target for target in targets if target in folded]


def _install_fake_service(monkeypatch) -> None:
    monkeypatch.setattr(suggestion_postprocess, "_svc", lambda: _FakeService())


def test_sanitize_context_term_values_drops_noisy_wrapper_for_phong_k(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["thông tin về Phòng K"],
        keyword_phrases=["phong k"],
    )
    assert result == []


def test_sanitize_context_term_values_keeps_noi_xau(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["nói xấu về Trưởng nhóm Q"],
        keyword_phrases=["truong nhom q"],
    )
    assert result == ["noi xau"]


def test_sanitize_context_term_values_keeps_tai_lieu_noi_bo(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["tài liệu nội bộ của Trung tâm M"],
        keyword_phrases=["trung tam m"],
    )
    assert result == ["tai lieu noi bo"]


def test_sanitize_context_term_values_keeps_business_phrase_and_modifier(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["kế hoạch mở rộng thị trường nội bộ của Công ty Z", "nội bộ"],
        keyword_phrases=["cong ty z"],
    )
    assert result == ["ke hoach mo rong thi truong", "noi bo"]


def test_sanitize_context_term_values_keeps_quy_trinh_and_noi_bo(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["quy trình xử lý sự cố nội bộ của Dự án C", "nội bộ"],
        keyword_phrases=["du an c"],
    )
    assert result == ["quy trinh xu ly su co", "noi bo"]
def test_sanitize_context_term_values_drops_generic_entity_leftover(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["phong"],
        keyword_phrases=["phong k"],
    )
    assert result == []


def test_sanitize_context_term_values_drops_generic_entity_subset_of_keyword(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["cong ty"],
        keyword_phrases=["cong ty z"],
    )
    assert result == []


def test_case_a_phong_t_context_empty(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["thong tin ve phong"],
        keyword_phrases=["phong t"],
    )
    assert result == []


def test_case_b_bo_phan_x_context_empty(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["cac noi dung", "bo phan"],
        keyword_phrases=["bo phan x"],
    )
    assert result == []


def test_case_c_trung_tam_y_context_empty(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["lien quan den"],
        keyword_phrases=["trung tam y"],
    )
    assert result == []


def test_case_d_nhan_vien_b_keeps_noi_xau(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["noi xau ve nhan vien b"],
        keyword_phrases=["nhan vien b"],
    )
    assert result == ["noi xau"]


def test_case_e_phong_r_keeps_tai_lieu_noi_bo(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["tai lieu noi bo cua phong r"],
        keyword_phrases=["phong r"],
    )
    assert result == ["tai lieu noi bo"]


def test_case_f_phong_k_keeps_thong_tin_mat(monkeypatch):
    _install_fake_service(monkeypatch)
    result = suggestion_postprocess._sanitize_context_term_values(
        ["thong tin mat cua"],
        keyword_phrases=["phong k"],
    )
    assert result == ["thong tin mat"]
