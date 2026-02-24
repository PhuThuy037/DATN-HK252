from __future__ import annotations

from dataclasses import asdict
from typing import Any


def entity_to_dict(e: Any) -> dict[str, Any]:
    # e là dataclass Entity của LocalRegexDetector
    try:
        return asdict(e)
    except Exception:
        # fallback
        return {
            "type": getattr(e, "type", None),
            "start": getattr(e, "start", None),
            "end": getattr(e, "end", None),
            "score": getattr(e, "score", None),
            "source": getattr(e, "source", None),
            "text": getattr(e, "text", None),
            "metadata": getattr(e, "metadata", {}) or {},
        }


def rulematch_to_dict(r: Any) -> dict[str, Any]:
    return {
        "rule_id": str(getattr(r, "rule_id")),
        "stable_key": getattr(r, "stable_key", None),
        "name": getattr(r, "name", None),
        "action": getattr(
            getattr(r, "action", None), "value", str(getattr(r, "action", None))
        ),
        "priority": getattr(r, "priority", None),
    }