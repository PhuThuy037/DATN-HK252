from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
import time
from threading import RLock
from typing import Any, Optional
import unicodedata
from uuid import UUID

from sqlmodel import Session, select

from app.common.enums import RuleAction
from app.rule.model import Rule
from app.rule.user_rule_override import UserRuleOverride


@dataclass(slots=True)
class RuleMatch:
    rule_id: UUID
    stable_key: str
    name: str
    action: RuleAction
    priority: int


@dataclass(slots=True, frozen=True)
class RuleRuntime:
    rule_id: UUID
    stable_key: str
    name: str
    action: RuleAction
    priority: int
    conditions: dict[str, Any]


class RuleEngine:
    """
    Match rules from Rule.conditions (JSONB DSL).

    Runtime layering:
    - Personal: enabled global rules, with optional per-user enabled override.
    - Company:
      1) company override > company custom > global default
      2) override(enabled=false) disables matching global stable_key for that company
      3) final resolved rules are sorted by priority DESC
    """

    _CACHE_TTL_SECONDS = 5.0
    _cache_lock = RLock()
    _rules_cache: dict[
        tuple[Optional[UUID], Optional[UUID]], tuple[float, list[RuleRuntime]]
    ] = {}

    @classmethod
    def _cache_key(
        cls, *, company_id: Optional[UUID], user_id: Optional[UUID]
    ) -> tuple[Optional[UUID], Optional[UUID]]:
        # User-level key is only relevant for personal scope.
        return (company_id, user_id if company_id is None else None)

    @classmethod
    def invalidate_cache(
        cls, company_id: Optional[UUID] = None, user_id: Optional[UUID] = None
    ) -> None:
        with cls._cache_lock:
            if company_id is None and user_id is None:
                cls._rules_cache.clear()
                return
            cls._rules_cache.pop(
                cls._cache_key(company_id=company_id, user_id=user_id), None
            )

    def _get_cached_rules(
        self, *, company_id: Optional[UUID], user_id: Optional[UUID]
    ) -> list[RuleRuntime] | None:
        cache_key = self._cache_key(company_id=company_id, user_id=user_id)
        with self._cache_lock:
            entry = self._rules_cache.get(cache_key)
            if not entry:
                return None
            expires_at, rules = entry
            if expires_at <= time.monotonic():
                self._rules_cache.pop(cache_key, None)
                return None
            return list(rules)

    def _set_cached_rules(
        self,
        *,
        company_id: Optional[UUID],
        user_id: Optional[UUID],
        rules: list[RuleRuntime],
    ) -> None:
        cache_key = self._cache_key(company_id=company_id, user_id=user_id)
        with self._cache_lock:
            self._rules_cache[cache_key] = (
                time.monotonic() + self._CACHE_TTL_SECONDS,
                list(rules),
            )

    def load_rules(
        self,
        *,
        session: Session,
        company_id: Optional[UUID],
        user_id: Optional[UUID] = None,
    ) -> list[RuleRuntime]:
        cached = self._get_cached_rules(company_id=company_id, user_id=user_id)
        if cached is not None:
            return cached

        rules = self._load_rules_uncached(
            session=session,
            company_id=company_id,
            user_id=user_id,
        )
        self._set_cached_rules(company_id=company_id, user_id=user_id, rules=rules)
        return list(rules)

    def _load_rules_uncached(
        self,
        *,
        session: Session,
        company_id: Optional[UUID],
        user_id: Optional[UUID],
    ) -> list[RuleRuntime]:
        if company_id is None:
            stmt = (
                select(Rule)
                .where(Rule.company_id.is_(None))
                .order_by(Rule.priority.desc(), Rule.created_at.desc(), Rule.id.desc())
            )
            rows = list(session.exec(stmt).all())

            override_by_key: dict[str, bool] = {}
            if user_id is not None:
                overrides = list(
                    session.exec(
                        select(UserRuleOverride).where(
                            UserRuleOverride.user_id == user_id
                        )
                    ).all()
                )
                override_by_key = {
                    str(r.stable_key): bool(r.enabled)
                    for r in overrides
                    if str(r.stable_key or "").strip()
                }

            out: list[RuleRuntime] = []
            for r in rows:
                effective_enabled = override_by_key.get(
                    str(r.stable_key), bool(r.enabled)
                )
                if effective_enabled:
                    out.append(self._to_runtime(r))
            return out

        global_rows = list(
            session.exec(
                select(Rule)
                .where(Rule.company_id.is_(None))
                .order_by(Rule.created_at.desc(), Rule.id.desc())
            ).all()
        )
        company_rows = list(
            session.exec(
                select(Rule)
                .where(Rule.company_id == company_id)
                .order_by(Rule.created_at.desc(), Rule.id.desc())
            ).all()
        )

        global_by_key: dict[str, Rule] = {}
        for g in global_rows:
            if g.stable_key not in global_by_key:
                global_by_key[g.stable_key] = g

        global_keys = set(global_by_key.keys())

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
        return [self._to_runtime(r) for r in resolved]

    def evaluate(
        self,
        *,
        session: Session,
        company_id: Optional[UUID],
        user_id: Optional[UUID] = None,
        entities: list[Any],
        signals: dict[str, Any],
    ) -> list[RuleMatch]:
        signals = self._normalize_signals(signals)

        rules = self.load_rules(session=session, company_id=company_id, user_id=user_id)
        matches: list[RuleMatch] = []

        for r in rules:
            try:
                if self._match_conditions(
                    r.conditions or {}, entities=entities, signals=signals
                ):
                    matches.append(
                        RuleMatch(
                            rule_id=r.rule_id,
                            stable_key=r.stable_key,
                            name=r.name,
                            action=r.action,
                            priority=r.priority,
                        )
                    )
            except Exception:
                continue

        return matches

    def _match_conditions(
        self,
        node: dict[str, Any],
        *,
        entities: list[Any],
        signals: dict[str, Any],
    ) -> bool:
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
            source = node.get("source")
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

            if "exists" in s:
                want = bool(s["exists"])
                return (value is not None) if want else (value is None)

            if "equals" in s:
                return self._signal_equals(value, s["equals"])
            if "in" in s:
                return any(
                    self._signal_equals(value, candidate)
                    for candidate in (s["in"] or [])
                )

            if "contains" in s:
                needle = s["contains"]
                if isinstance(value, list):
                    return any(self._signal_equals(item, needle) for item in value)
                if isinstance(value, str):
                    return self._contains_text(value, str(needle))
                return False

            if "any_of" in s:
                needles = s.get("any_of") or []
                if isinstance(value, list):
                    return any(
                        self._signal_equals(item, needle)
                        for item in value
                        for needle in needles
                    )
                if isinstance(value, str):
                    return any(
                        self._contains_text(value, str(needle)) for needle in needles
                    )
                return False

            if "gte" in s:
                return self._to_float(value) >= float(s["gte"])
            if "lte" in s:
                return self._to_float(value) <= float(s["lte"])
            if "gt" in s:
                return self._to_float(value) > float(s["gt"])
            if "lt" in s:
                return self._to_float(value) < float(s["lt"])

            if "startswith" in s:
                return isinstance(value, str) and self._starts_with_text(
                    value, str(s["startswith"])
                )

            if "regex" in s:
                if not isinstance(value, str):
                    return False
                return re.search(str(s["regex"]), value) is not None

            raise ValueError(f"Unsupported signal operator: {s}")

        raise ValueError(f"Unsupported condition node: {node}")

    def _fold_text(self, value: str) -> str:
        raw = str(value or "").lower().replace("\u0111", "d")
        normalized = unicodedata.normalize("NFKD", raw)
        no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", no_marks).strip()

    def _signal_equals(self, left: Any, right: Any) -> bool:
        if isinstance(left, str) and isinstance(right, str):
            return self._fold_text(left) == self._fold_text(right)
        return left == right

    def _contains_text(self, haystack: str, needle: str) -> bool:
        return self._fold_text(needle) in self._fold_text(haystack)

    def _starts_with_text(self, value: str, prefix: str) -> bool:
        return self._fold_text(value).startswith(self._fold_text(prefix))

    def _has_entity(
        self,
        entities: list[Any],
        entity_type: str,
        *,
        min_score: float,
        max_score: Optional[float],
        source: Any,
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
        cur: Any = signals
        for part in field.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur

    def _normalize_signals(self, signals: dict[str, Any]) -> dict[str, Any]:
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

    def _to_runtime(self, rule: Rule) -> RuleRuntime:
        return RuleRuntime(
            rule_id=rule.id,
            stable_key=str(rule.stable_key),
            name=str(rule.name),
            action=rule.action,
            priority=int(rule.priority),
            conditions=deepcopy(rule.conditions or {}),
        )
