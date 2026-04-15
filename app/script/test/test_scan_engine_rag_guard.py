from __future__ import annotations

from app.decision.scan_engine_local import ScanEngineLocal


def test_should_call_rag_skips_example_placeholder_secret_text() -> None:
    engine = ScanEngineLocal.__new__(ScanEngineLocal)

    should_call = engine._should_call_rag(
        text="Trong slide minh viet mau sk-test-xxxxx de minh hoa format key, khong phai secret that.",
        sec_decision="ALLOW",
        sec_score=0.0,
        persona="dev",
        context_keywords=["secret"],
        entities=[],
        spoken_entities=[],
    )

    assert should_call is False
