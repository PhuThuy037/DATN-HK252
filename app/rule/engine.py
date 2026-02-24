from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from sqlmodel import Session, select

from app.rule.model import Rule
from app.common.enums import RuleAction


@dataclass(slots=True)
class RuleMatch:
    rule_id: UUID
    stable_key: str
    name: str
    action: RuleAction
    priority: int


class RuleEngine:
    """
    Match rule theo DSL trong Rule.conditions (JSONB).
    Load rules: (company_id = X OR NULL) AND enabled=true ORDER BY priority DESC
    """

    def load_rules(self, *, session: Session, company_id: Optional[UUID]) -> list[Rule]:
        stmt = (
            select(Rule)
            .where(Rule.enabled.is_(True))
            .where((Rule.company_id == company_id) | (Rule.company_id.is_(None)))
            .order_by(Rule.priority.desc())
        )
        return list(session.exec(stmt).all())

    def evaluate(
        self,
        *,
        session: Session,
        company_id: Optional[UUID],
        entities: list[Any],  # list Entity từ local_regex
        signals: dict[str, Any],  # signals từ ContextScorer + security...
    ) -> list[RuleMatch]:
        rules = self.load_rules(session=session, company_id=company_id)
        matches: list[RuleMatch] = []

        for r in rules:
            if self._match_conditions(r.conditions, entities=entities, signals=signals):
                matches.append(
                    RuleMatch(
                        rule_id=r.id,
                        stable_key=r.stable_key,
                        name=r.name,
                        action=r.action,
                        priority=r.priority,
                    )
                )
        return matches

    # ---------------- DSL ----------------
    def _match_conditions(
        self,
        node: dict[str, Any],
        *,
        entities: list[Any],
        signals: dict[str, Any],
    ) -> bool:
        # nodes:
        # {"any": [node...]}
        # {"all": [node...]}
        # {"not": node}
        # leaf:
        # {"entity_type": "CCCD", "min_score": 0.85, "source": "local_regex"}
        # {"signal": {"field": "persona", "equals": "dev"}}

        if "any" in node:
            return any(
                self._match_conditions(n, entities=entities, signals=signals)
                for n in node["any"]
            )

        if "all" in node:
            return all(
                self._match_conditions(n, entities=entities, signals=signals)
                for n in node["all"]
            )

        if "not" in node:
            return not self._match_conditions(
                node["not"], entities=entities, signals=signals
            )

        if "entity_type" in node:
            et = str(node["entity_type"])
            min_score = float(node.get("min_score", 0.0))
            source = node.get("source")  # optional
            return self._has_entity(entities, et, min_score=min_score, source=source)

        if "signal" in node:
            s = node["signal"]
            field = str(s["field"])
            value = self._get_signal(signals, field)

            if "equals" in s:
                return value == s["equals"]
            if "in" in s:
                return value in s["in"]
            if "contains" in s:
                # list or str
                needle = s["contains"]
                if isinstance(value, list):
                    return needle in value
                if isinstance(value, str):
                    return needle in value
                return False

            raise ValueError(f"Unsupported signal operator: {s}")

        raise ValueError(f"Unsupported condition node: {node}")

    def _has_entity(
        self,
        entities: list[Any],
        entity_type: str,
        *,
        min_score: float,
        source: Optional[str],
    ) -> bool:
        for e in entities:
            if getattr(e, "type", None) != entity_type:
                continue
            if float(getattr(e, "score", 0.0)) < min_score:
                continue
            if source and getattr(e, "source", None) != source:
                continue
            return True
        return False

    def _get_signal(self, signals: dict[str, Any], field: str) -> Any:
        # supports dot path: "security.prompt_injection"
        cur: Any = signals
        for part in field.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur