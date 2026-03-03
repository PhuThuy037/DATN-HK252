# app/decision/rule_layering.py (hoặc nhét vào scan_engine_local.py cũng được)

from __future__ import annotations
from typing import Iterable

MASK_ENTITY_KEYS = {
    "global.pii.phone.mask",
    "global.pii.email.mask",
    "global.pii.tax.mask",
    "global.pii.credit_card.mask",
}
RAG_MASK_KEY = "global.security.rag.mask"


def compact_matches(matches: list, *, final_action: str) -> list:
    """
    - BLOCK: giữ tất cả block (hoặc giữ top 1 tuỳ mày)
    - MASK: chỉ giữ 1 rule mask quan trọng nhất:
        ưu tiên entity mask rule > rag.mask
    """
    if final_action != "mask":
        return matches

    # 1) lấy ra mask matches
    mask_matches = [m for m in matches if str(m.action).lower() == "mask"]
    if not mask_matches:
        return matches

    # 2) ưu tiên entity mask rule
    entity_masks = [m for m in mask_matches if m.stable_key in MASK_ENTITY_KEYS]
    if entity_masks:
        winner = max(entity_masks, key=lambda m: int(m.priority))
    else:
        # nếu chỉ có rag.mask thì giữ rag.mask
        winner = max(mask_matches, key=lambda m: int(m.priority))

    # 3) giữ winner + những rule non-mask (block/allow…)
    keep = [m for m in matches if str(m.action).lower() != "mask"]
    keep.append(winner)
    # sort lại cho đẹp
    keep.sort(key=lambda m: int(m.priority), reverse=True)
    return keep