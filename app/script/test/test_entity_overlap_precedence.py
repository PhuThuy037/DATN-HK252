from __future__ import annotations

from types import SimpleNamespace

from app.decision.entity_merger import EntityMerger, MergeConfig


def test_entity_merger_prefers_api_secret_over_nested_phone() -> None:
    merger = EntityMerger(
        MergeConfig(
            overlap_threshold=0.80,
            prefer_source_order=("local_regex", "spoken_norm", "presidio"),
        )
    )
    entities = [
        SimpleNamespace(
            type="API_SECRET",
            start=10,
            end=37,
            score=0.98,
            source="local_regex",
        ),
        SimpleNamespace(
            type="PHONE",
            start=26,
            end=37,
            score=0.95,
            source="local_regex",
        ),
    ]

    merged = merger.merge(entities)

    assert len(merged) == 1
    assert merged[0].type == "API_SECRET"
