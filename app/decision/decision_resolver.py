from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.common.enums import RuleAction
from app.rule.engine import RuleMatch


@dataclass(slots=True)
class DecisionResult:
    final_action: RuleAction
    matched: list[RuleMatch]
    chosen: Optional[RuleMatch]


class DecisionResolver:
    """
    Resolve final action khi có nhiều rule match.
    MVP policy:
      - Nếu có BLOCK => BLOCK (ưu tiên rule BLOCK có priority cao nhất)
      - else nếu có MASK => MASK (priority cao nhất)
      - else => ALLOW (hoặc ALLOW_LOG nếu enum của mày có)
    """

    def resolve(self, matches: list[RuleMatch]) -> DecisionResult:
        if not matches:
            # Tuỳ enum của mày, nếu không có ALLOW thì dùng ALLOW_LOG
            allow = (
                RuleAction.allow
                if hasattr(RuleAction, "allow")
                else RuleAction.allow_log
            )
            return DecisionResult(final_action=allow, matched=[], chosen=None)

        # sort by priority desc
        matches_sorted = sorted(matches, key=lambda m: m.priority, reverse=True)

        blocks = [m for m in matches_sorted if str(m.action).lower() == "block"]
        if blocks:
            return DecisionResult(
                final_action=blocks[0].action, matched=matches_sorted, chosen=blocks[0]
            )

        masks = [m for m in matches_sorted if str(m.action).lower() == "mask"]
        if masks:
            return DecisionResult(
                final_action=masks[0].action, matched=matches_sorted, chosen=masks[0]
            )

        return DecisionResult(
            final_action=matches_sorted[0].action,
            matched=matches_sorted,
            chosen=matches_sorted[0],
        )