# app/rule/seed.py
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from sqlmodel import Session, select

from app.rule.model import Rule
from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity


def _to_enum(enum_cls, value: str):
    try:
        return enum_cls(value)  # value = "message", "block"...
    except Exception:
        return enum_cls[value]  # value = "MESSAGE", "BLOCK"


class RuleSeeder:
    def __init__(self, yaml_path: str | Path):
        self.yaml_path = Path(yaml_path)

    def load_yaml(self) -> dict[str, Any]:
        data = yaml.safe_load(self.yaml_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or "rules" not in data:
            raise ValueError("Invalid seed_rules.yaml format: missing 'rules'")
        return data

    def upsert_global_rules(self, *, session: Session, created_by_user_id: UUID) -> int:
        data = self.load_yaml()
        defaults: dict[str, Any] = data.get("defaults") or {}
        rules: list[dict[str, Any]] = data["rules"]

        processed = 0
        for r in rules:
            key = r["key"]
            name = r["name"]
            description = r.get("description")

            scope = _to_enum(
                RuleScope, r.get("scope", defaults.get("scope", "message"))
            )
            action = _to_enum(RuleAction, r["action"])
            severity = _to_enum(
                RuleSeverity, r.get("severity", defaults.get("severity", "medium"))
            )
            priority = int(r.get("priority", defaults.get("priority", 0)))
            rag_mode = _to_enum(
                RagMode, r.get("rag_mode", defaults.get("rag_mode", "off"))
            )
            enabled = bool(r.get("enabled", defaults.get("enabled", True)))
            conditions_version = int(
                r.get("conditions_version", defaults.get("conditions_version", 1))
            )

            conditions = r.get("conditions")
            if not isinstance(conditions, dict):
                raise ValueError(f"Rule '{key}' missing conditions dict")

            existing = session.exec(
                select(Rule)
                .where(Rule.company_id.is_(None))
                .where(Rule.stable_key == key)
            ).first()

            if existing:
                existing.name = name
                existing.description = description
                existing.scope = scope
                existing.action = action
                existing.severity = severity
                existing.priority = priority
                existing.rag_mode = rag_mode
                existing.enabled = enabled
                existing.conditions_version = conditions_version
                existing.conditions = conditions
            else:
                session.add(
                    Rule(
                        company_id=None,
                        stable_key=key,
                        name=name,
                        description=description,
                        scope=scope,
                        conditions=conditions,
                        conditions_version=conditions_version,
                        action=action,
                        severity=severity,
                        priority=priority,
                        rag_mode=rag_mode,
                        enabled=enabled,
                        created_by=created_by_user_id,
                    )
                )

            processed += 1

        session.commit()
        return processed