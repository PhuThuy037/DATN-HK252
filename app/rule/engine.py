from __future__ import annotations

import re
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

    Runtime layering:
    - Personal: enabled global rules.
    - Company:
      1) company override > company custom > global default
      2) override(enabled=false) disables matching global stable_key for that company
      3) final resolved rules are sorted by priority DESC
    """

    def load_rules(self, *, session: Session, company_id: Optional[UUID]) -> list[Rule]:
        # Personal mode: only enabled global rules.
        if company_id is None:
            stmt = (
                select(Rule)
                .where(Rule.company_id.is_(None))
                .where(Rule.enabled.is_(True))
                .order_by(Rule.priority.desc())
            )
            return list(session.exec(stmt).all())

        # Company mode precedence:
        # company override > company custom > global default
        # and override(enabled=false) disables corresponding global rule for this company.
        global_rows = list(
            session.exec(
                select(Rule)
                .where(Rule.company_id.is_(None))
                .order_by(Rule.created_at.desc())
            ).all()
        )
        company_rows = list(
            session.exec(
                select(Rule)
                .where(Rule.company_id == company_id)
                .order_by(Rule.created_at.desc())
            ).all()
        )

        global_by_key: dict[str, Rule] = {}
        for g in global_rows:
            if g.stable_key not in global_by_key:
                global_by_key[g.stable_key] = g

        global_keys = set(global_by_key.keys())

        # Keep the newest company row for each global stable_key as override.
        override_by_key: dict[str, Rule] = {}
        custom_enabled: list[Rule] = []
        for c in company_rows:
            if c.stable_key in global_keys:
                if c.stable_key not in override_by_key:
                    override_by_key[c.stable_key] = c
                continue
            if c.enabled:
                custom_enabled.append(c)

        resolved: list[Rule] = []

        for stable_key, g in global_by_key.items():
            override = override_by_key.get(stable_key)
            if override is None:
                if g.enabled:
                    resolved.append(g)
                continue

            if override.enabled:
                resolved.append(override)
            # else: explicit company disable, skip both override and global.

        resolved.extend(custom_enabled)
        resolved.sort(key=lambda r: int(r.priority), reverse=True)
        return resolved

    def evaluate(
        self,
        *,
        session: Session,
        company_id: Optional[UUID],
        entities: list[Any],
        signals: dict[str, Any],
    ) -> list[RuleMatch]:
        # đảm bảo rag signal luôn có shape chuẩn
        signals = self._normalize_signals(signals)

        rules = self.load_rules(session=session, company_id=company_id)
        matches: list[RuleMatch] = []

        for r in rules:
            try:
                if self._match_conditions(
                    r.conditions or {}, entities=entities, signals=signals
                ):
                    matches.append(
                        RuleMatch(
                            rule_id=r.id,
                            stable_key=r.stable_key,
                            name=r.name,
                            action=r.action,
                            priority=r.priority,
                        )
                    )
            except Exception:
                # MVP production-like: rule nào lỗi conditions thì skip, đừng crash pipeline
                continue

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
        # leaf entity:
        # {"entity_type": "CCCD", "min_score": 0.85, "source": "local_regex" | ["local_regex","spoken_norm"]}
        # leaf signal:
        # {"signal": {"field": "persona", "equals": "dev"}}

        if not isinstance(node, dict):
            raise ValueError(f"Condition node must be dict, got: {type(node)}")

        if "any" in node:
            children = node.get("any") or []
            return any(
                self._match_conditions(n, entities=entities, signals=signals)
                for n in children
            )

        if "all" in node:
            children = node.get("all") or []
            return all(
                self._match_conditions(n, entities=entities, signals=signals)
                for n in children
            )

        if "not" in node:
            return not self._match_conditions(
                node["not"], entities=entities, signals=signals
            )

        if "entity_type" in node:
            et = str(node["entity_type"])
            min_score = float(node.get("min_score", 0.0))
            max_score = node.get("max_score")
            max_score_f = float(max_score) if max_score is not None else None
            source = node.get("source")  # str | list[str] | None
            return self._has_entity(
                entities,
                et,
                min_score=min_score,
                max_score=max_score_f,
                source=source,
            )

        if "signal" in node:
            s = node["signal"]
            if not isinstance(s, dict):
                raise ValueError(f"signal leaf must be dict, got {type(s)}")

            field = str(s.get("field", ""))
            value = self._get_signal(signals, field)

            # exists
            if "exists" in s:
                want = bool(s["exists"])
                return (value is not None) if want else (value is None)

            # equals / in
            if "equals" in s:
                return value == s["equals"]
            if "in" in s:
                return value in (s["in"] or [])

            # contains / any_of
            if "contains" in s:
                needle = s["contains"]
                if isinstance(value, list):
                    return needle in value
                if isinstance(value, str):
                    return str(needle) in value
                return False

            if "any_of" in s:
                # value phải là list/str và chỉ cần match 1 cái trong list
                needles = s.get("any_of") or []
                if isinstance(value, list):
                    return any(n in value for n in needles)
                if isinstance(value, str):
                    return any(str(n) in value for n in needles)
                return False

            # numeric comparisons
            if "gte" in s:
                return self._to_float(value) >= float(s["gte"])
            if "lte" in s:
                return self._to_float(value) <= float(s["lte"])
            if "gt" in s:
                return self._to_float(value) > float(s["gt"])
            if "lt" in s:
                return self._to_float(value) < float(s["lt"])

            # startswith
            if "startswith" in s:
                return isinstance(value, str) and value.startswith(str(s["startswith"]))

            # regex (string)
            if "regex" in s:
                if not isinstance(value, str):
                    return False
                return re.search(str(s["regex"]), value) is not None

            raise ValueError(f"Unsupported signal operator: {s}")

        raise ValueError(f"Unsupported condition node: {node}")

    def _has_entity(
        self,
        entities: list[Any],
        entity_type: str,
        *,
        min_score: float,
        max_score: Optional[float],
        source: Any,  # None | str | list[str]
    ) -> bool:
        allowed_sources: Optional[set[str]] = None
        if isinstance(source, str):
            allowed_sources = {source}
        elif isinstance(source, list):
            allowed_sources = {str(x) for x in source}

        for e in entities:
            if getattr(e, "type", None) != entity_type:
                continue

            score = float(getattr(e, "score", 0.0))
            if score < min_score:
                continue
            if max_score is not None and score > max_score:
                continue

            if allowed_sources is not None:
                if str(getattr(e, "source", "")) not in allowed_sources:
                    continue

            return True

        return False

    def _get_signal(self, signals: dict[str, Any], field: str) -> Any:
        # supports dot path: "security.prompt_injection_block", "rag.decision"
        cur: Any = signals
        for part in field.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur

    def _normalize_signals(self, signals: dict[str, Any]) -> dict[str, Any]:
        # đảm bảo signals["rag"] luôn có shape nhất quán
        rag = signals.get("rag")
        if not isinstance(rag, dict):
            signals["rag"] = {"decision": "SKIPPED", "confidence": 0.0, "rule_keys": []}
        else:
            rag.setdefault("decision", "SKIPPED")
            rag.setdefault("confidence", 0.0)
            rag.setdefault("rule_keys", [])
        return signals

    def _to_float(self, v: Any) -> float:
        try:
            return float(v)
        except Exception:
            return 0.0
