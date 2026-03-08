from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.common.error_codes import ErrorCode
from app.common.errors import AppError
from app.common.enums import MemberRole, MemberStatus
from app.company.model import Company
from app.company_member.model import CompanyMember
from app.permissions.core import forbid, not_found
from app.permissions.loaders.conversation import load_company_member_active_or_403
from app.rule.engine import RuleEngine
from app.rule.model import Rule
from app.rule.schemas import (
    CompanyRuleCreateIn,
    CompanyRuleOut,
    CompanyRuleUpdateIn,
    PersonalRuleOut,
    RuleChangeLogOut,
    RuleOrigin,
)
from app.rule.user_rule_override import UserRuleOverride
from app.rule_change_log.model import RuleChangeLog


def _load_company_or_404(*, session: Session, company_id: UUID) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise not_found("Company not found", field="company_id")
    return company


def _require_company_member(
    *, session: Session, company_id: UUID, user_id: UUID
) -> CompanyMember:
    return load_company_member_active_or_403(
        session=session,
        company_id=company_id,
        user_id=user_id,
    )


def _require_company_admin(
    *, session: Session, company_id: UUID, user_id: UUID
) -> None:
    member = _require_company_member(
        session=session,
        company_id=company_id,
        user_id=user_id,
    )
    if member.role != MemberRole.company_admin:
        raise forbid(
            "Company admin required",
            field="company_id",
            reason="not_company_admin",
        )


def _has_active_company_membership(*, session: Session, user_id: UUID) -> bool:
    row = session.exec(
        select(CompanyMember.id)
        .where(CompanyMember.user_id == user_id)
        .where(CompanyMember.status == MemberStatus.active)
        .limit(1)
    ).first()
    return row is not None


def _require_no_active_company_membership(*, session: Session, user_id: UUID) -> None:
    if _has_active_company_membership(session=session, user_id=user_id):
        raise forbid(
            "Personal rule management is not allowed for company members",
            field="user_id",
            reason="personal_rule_forbidden_for_company_member",
        )


def _normalize_non_empty(*, value: str | None, field: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid {field}",
            details=[{"field": field, "reason": "empty_after_trim"}],
        )
    return normalized


def _normalize_stable_key(*, stable_key: str) -> str:
    return _normalize_non_empty(value=stable_key, field="stable_key")


def _validate_conditions_node(node: Any) -> None:
    if not isinstance(node, dict):
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Invalid rule conditions",
            details=[{"field": "conditions", "reason": "condition_node_not_dict"}],
        )

    keys = set(node.keys())
    control_keys = {"any", "all", "not"}

    if keys & control_keys:
        if "any" in node:
            children = node.get("any")
            if not isinstance(children, list):
                raise AppError(
                    422,
                    ErrorCode.VALIDATION_ERROR,
                    "Invalid rule conditions",
                    details=[{"field": "conditions.any", "reason": "must_be_list"}],
                )
            for child in children:
                _validate_conditions_node(child)
            return

        if "all" in node:
            children = node.get("all")
            if not isinstance(children, list):
                raise AppError(
                    422,
                    ErrorCode.VALIDATION_ERROR,
                    "Invalid rule conditions",
                    details=[{"field": "conditions.all", "reason": "must_be_list"}],
                )
            for child in children:
                _validate_conditions_node(child)
            return

        _validate_conditions_node(node.get("not"))
        return

    if "entity_type" in node:
        entity_type = str(node.get("entity_type", "")).strip()
        if not entity_type:
            raise AppError(
                422,
                ErrorCode.VALIDATION_ERROR,
                "Invalid rule conditions",
                details=[{"field": "conditions.entity_type", "reason": "empty"}],
            )
        return

    if "signal" in node:
        signal = node.get("signal")
        if not isinstance(signal, dict):
            raise AppError(
                422,
                ErrorCode.VALIDATION_ERROR,
                "Invalid rule conditions",
                details=[{"field": "conditions.signal", "reason": "must_be_object"}],
            )
        field = str(signal.get("field", "")).strip()
        if not field:
            raise AppError(
                422,
                ErrorCode.VALIDATION_ERROR,
                "Invalid rule conditions",
                details=[{"field": "conditions.signal.field", "reason": "empty"}],
            )
        return

    raise AppError(
        422,
        ErrorCode.VALIDATION_ERROR,
        "Invalid rule conditions",
        details=[{"field": "conditions", "reason": "unsupported_node"}],
    )


def _validate_conditions(*, conditions: dict[str, Any]) -> None:
    _validate_conditions_node(conditions)


def _global_stable_keys(*, session: Session) -> set[str]:
    rows = session.exec(select(Rule.stable_key).where(Rule.company_id.is_(None))).all()
    return {str(x) for x in rows}


def _classify_origin(*, rule: Rule, global_keys: set[str]) -> RuleOrigin:
    if rule.company_id is None:
        return RuleOrigin.global_default
    if rule.stable_key in global_keys:
        return RuleOrigin.company_override
    return RuleOrigin.company_custom


def _to_rule_out(
    *, rule: Rule, origin: RuleOrigin, is_admin: bool = True
) -> CompanyRuleOut:
    return CompanyRuleOut(
        id=rule.id,
        company_id=rule.company_id,
        stable_key=rule.stable_key,
        name=rule.name,
        description=rule.description,
        scope=rule.scope,
        conditions=rule.conditions,
        conditions_version=rule.conditions_version,
        action=rule.action,
        severity=rule.severity,
        priority=rule.priority,
        rag_mode=rule.rag_mode,
        enabled=rule.enabled,
        created_by=rule.created_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        origin=origin,
        can_edit_action=is_admin and origin == RuleOrigin.company_custom,
        can_soft_delete=is_admin and origin != RuleOrigin.global_default,
    )


def _to_personal_rule_out(
    *,
    rule: Rule,
    override_enabled: bool | None,
    can_toggle_enabled: bool,
) -> PersonalRuleOut:
    effective_enabled = (
        bool(override_enabled) if override_enabled is not None else bool(rule.enabled)
    )
    return PersonalRuleOut(
        id=rule.id,
        stable_key=rule.stable_key,
        name=rule.name,
        description=rule.description,
        scope=rule.scope,
        conditions=rule.conditions,
        conditions_version=rule.conditions_version,
        action=rule.action,
        severity=rule.severity,
        priority=rule.priority,
        rag_mode=rule.rag_mode,
        enabled=effective_enabled,
        default_enabled=bool(rule.enabled),
        has_override=override_enabled is not None,
        can_toggle_enabled=can_toggle_enabled,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def _to_rule_change_out(*, row: RuleChangeLog) -> RuleChangeLogOut:
    return RuleChangeLogOut(
        id=row.id,
        company_id=row.company_id,
        rule_id=row.rule_id,
        actor_user_id=row.actor_user_id,
        action=row.action,
        changed_fields=list(row.changed_fields or []),
        before_json=row.before_json,
        after_json=row.after_json,
        created_at=row.created_at,
    )


def _snapshot_rule(*, rule: Rule) -> dict[str, Any]:
    return {
        "id": str(rule.id),
        "company_id": str(rule.company_id) if rule.company_id else None,
        "stable_key": rule.stable_key,
        "name": rule.name,
        "description": rule.description,
        "scope": rule.scope.value,
        "conditions": deepcopy(rule.conditions),
        "conditions_version": int(rule.conditions_version),
        "action": rule.action.value,
        "severity": rule.severity.value,
        "priority": int(rule.priority),
        "rag_mode": rule.rag_mode.value,
        "enabled": bool(rule.enabled),
    }


def _append_rule_change_log(
    *,
    session: Session,
    company_id: UUID,
    rule_id: UUID,
    actor_user_id: UUID,
    action: str,
    changed_fields: list[str],
    before_json: dict[str, Any] | None,
    after_json: dict[str, Any] | None,
) -> None:
    session.add(
        RuleChangeLog(
            company_id=company_id,
            rule_id=rule_id,
            actor_user_id=actor_user_id,
            action=action,
            changed_fields=changed_fields,
            before_json=before_json,
            after_json=after_json,
        )
    )


def _load_company_rule_by_stable_key(
    *, session: Session, company_id: UUID, stable_key: str
) -> Rule | None:
    rows = session.exec(
        select(Rule)
        .where(Rule.company_id == company_id)
        .where(Rule.stable_key == stable_key)
        .order_by(Rule.created_at.desc())
    ).all()
    if len(rows) > 1:
        raise AppError.conflict(
            ErrorCode.CONFLICT,
            "Duplicate company rules found for stable_key",
            field="stable_key",
        )
    return rows[0] if rows else None


def list_company_rules(
    *, session: Session, company_id: UUID, actor_user_id: UUID
) -> list[CompanyRuleOut]:
    _load_company_or_404(session=session, company_id=company_id)
    member = _require_company_member(
        session=session,
        company_id=company_id,
        user_id=actor_user_id,
    )
    is_admin = member.role == MemberRole.company_admin

    runtime_rules = RuleEngine().load_rules(session=session, company_id=company_id)
    rule_ids = [x.rule_id for x in runtime_rules]
    if not rule_ids:
        return []

    row_map = {
        r.id: r for r in session.exec(select(Rule).where(Rule.id.in_(rule_ids))).all()
    }
    global_keys = _global_stable_keys(session=session)

    out: list[CompanyRuleOut] = []
    for runtime in runtime_rules:
        row = row_map.get(runtime.rule_id)
        if row is None:
            continue
        out.append(
            _to_rule_out(
                rule=row,
                origin=_classify_origin(rule=row, global_keys=global_keys),
                is_admin=is_admin,
            )
        )
    return out


def list_company_rule_change_logs(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    limit: int,
) -> list[RuleChangeLogOut]:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(
        session=session, company_id=company_id, user_id=actor_user_id
    )

    safe_limit = max(1, min(int(limit), 200))
    rows = list(
        session.exec(
            select(RuleChangeLog)
            .where(RuleChangeLog.company_id == company_id)
            .order_by(RuleChangeLog.created_at.desc())
            .limit(safe_limit)
        ).all()
    )
    return [_to_rule_change_out(row=r) for r in rows]


def create_company_custom_rule(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    payload: CompanyRuleCreateIn,
) -> CompanyRuleOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(
        session=session, company_id=company_id, user_id=actor_user_id
    )

    stable_key = _normalize_stable_key(stable_key=payload.stable_key)
    name = _normalize_non_empty(value=payload.name, field="name")
    description = (payload.description or "").strip() or None
    _validate_conditions(conditions=payload.conditions)

    global_keys = _global_stable_keys(session=session)
    if stable_key in global_keys:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "stable_key is reserved by global rule",
            details=[{"field": "stable_key", "reason": "global_rule_key_reserved"}],
        )

    existed = _load_company_rule_by_stable_key(
        session=session,
        company_id=company_id,
        stable_key=stable_key,
    )
    if existed:
        raise AppError.conflict(
            ErrorCode.CONFLICT,
            "stable_key already exists in this company",
            field="stable_key",
        )

    row = Rule(
        company_id=company_id,
        stable_key=stable_key,
        name=name,
        description=description,
        scope=payload.scope,
        conditions=payload.conditions,
        conditions_version=1,
        action=payload.action,
        severity=payload.severity,
        priority=int(payload.priority),
        rag_mode=payload.rag_mode,
        enabled=bool(payload.enabled),
        created_by=actor_user_id,
    )
    session.add(row)
    _append_rule_change_log(
        session=session,
        company_id=company_id,
        rule_id=row.id,
        actor_user_id=actor_user_id,
        action="rule.create_custom",
        changed_fields=[
            "stable_key",
            "name",
            "description",
            "scope",
            "conditions",
            "conditions_version",
            "action",
            "severity",
            "priority",
            "rag_mode",
            "enabled",
        ],
        before_json=None,
        after_json=_snapshot_rule(rule=row),
    )
    session.commit()
    session.refresh(row)
    RuleEngine.invalidate_cache(company_id)
    return _to_rule_out(rule=row, origin=RuleOrigin.company_custom)


def update_company_rule(
    *,
    session: Session,
    company_id: UUID,
    rule_id: UUID,
    actor_user_id: UUID,
    payload: CompanyRuleUpdateIn,
) -> CompanyRuleOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(
        session=session, company_id=company_id, user_id=actor_user_id
    )

    row = session.get(Rule, rule_id)
    if not row:
        raise not_found("Rule not found", field="rule_id")
    if row.company_id != company_id:
        raise not_found("Rule not found", field="rule_id")

    global_keys = _global_stable_keys(session=session)
    origin = _classify_origin(rule=row, global_keys=global_keys)
    changed_fields = set(payload.model_fields_set)

    if not changed_fields:
        return _to_rule_out(rule=row, origin=origin)

    before_json = _snapshot_rule(rule=row)

    if origin == RuleOrigin.company_override:
        allowed_fields = {"enabled"}
        blocked = sorted(changed_fields - allowed_fields)
        if blocked:
            raise AppError(
                422,
                ErrorCode.VALIDATION_ERROR,
                "Only enabled can be changed for company override rule",
                details=[
                    {
                        "field": "rule",
                        "reason": "override_only_enabled_allowed",
                        "extra": {"blocked_fields": blocked},
                    }
                ],
            )

    if "name" in changed_fields and payload.name is not None:
        row.name = _normalize_non_empty(value=payload.name, field="name")
    if "description" in changed_fields:
        row.description = (payload.description or "").strip() or None
    if "scope" in changed_fields and payload.scope is not None:
        row.scope = payload.scope
    if "conditions" in changed_fields and payload.conditions is not None:
        _validate_conditions(conditions=payload.conditions)
        row.conditions = payload.conditions
        row.conditions_version = int(row.conditions_version or 1) + 1
    if "severity" in changed_fields and payload.severity is not None:
        row.severity = payload.severity
    if "priority" in changed_fields and payload.priority is not None:
        row.priority = int(payload.priority)
    if "rag_mode" in changed_fields and payload.rag_mode is not None:
        row.rag_mode = payload.rag_mode
    if "enabled" in changed_fields and payload.enabled is not None:
        row.enabled = bool(payload.enabled)

    if "action" in changed_fields and payload.action is not None:
        if origin != RuleOrigin.company_custom:
            raise AppError(
                422,
                ErrorCode.VALIDATION_ERROR,
                "Only company custom rule can change action",
                details=[{"field": "action", "reason": "action_change_not_allowed"}],
            )
        row.action = payload.action

    after_json = _snapshot_rule(rule=row)

    session.add(row)
    _append_rule_change_log(
        session=session,
        company_id=company_id,
        rule_id=row.id,
        actor_user_id=actor_user_id,
        action="rule.update",
        changed_fields=sorted(changed_fields),
        before_json=before_json,
        after_json=after_json,
    )
    session.commit()
    session.refresh(row)
    RuleEngine.invalidate_cache(company_id)
    return _to_rule_out(rule=row, origin=origin)


def soft_delete_company_rule(
    *,
    session: Session,
    company_id: UUID,
    rule_id: UUID,
    actor_user_id: UUID,
) -> CompanyRuleOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(
        session=session, company_id=company_id, user_id=actor_user_id
    )

    row = session.get(Rule, rule_id)
    if not row:
        raise not_found("Rule not found", field="rule_id")
    if row.company_id != company_id:
        raise not_found("Rule not found", field="rule_id")

    global_keys = _global_stable_keys(session=session)
    origin = _classify_origin(rule=row, global_keys=global_keys)

    before_json = _snapshot_rule(rule=row)
    row.enabled = False
    after_json = _snapshot_rule(rule=row)

    session.add(row)
    _append_rule_change_log(
        session=session,
        company_id=company_id,
        rule_id=row.id,
        actor_user_id=actor_user_id,
        action="rule.soft_delete",
        changed_fields=["enabled"],
        before_json=before_json,
        after_json=after_json,
    )
    session.commit()
    session.refresh(row)
    RuleEngine.invalidate_cache(company_id)
    return _to_rule_out(rule=row, origin=origin)


def toggle_global_rule_for_company(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    stable_key: str,
    enabled: bool,
) -> CompanyRuleOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(
        session=session, company_id=company_id, user_id=actor_user_id
    )

    normalized_key = _normalize_stable_key(stable_key=stable_key)

    global_rule = session.exec(
        select(Rule)
        .where(Rule.company_id.is_(None))
        .where(Rule.stable_key == normalized_key)
        .order_by(Rule.created_at.desc())
    ).first()
    if not global_rule:
        raise not_found("Global rule not found", field="stable_key")

    override = _load_company_rule_by_stable_key(
        session=session,
        company_id=company_id,
        stable_key=normalized_key,
    )

    before_json = _snapshot_rule(rule=override) if override is not None else None

    if override is None:
        override = Rule(
            company_id=company_id,
            stable_key=global_rule.stable_key,
            name=global_rule.name,
            description=global_rule.description,
            scope=global_rule.scope,
            conditions=deepcopy(global_rule.conditions),
            conditions_version=global_rule.conditions_version,
            action=global_rule.action,
            severity=global_rule.severity,
            priority=global_rule.priority,
            rag_mode=global_rule.rag_mode,
            enabled=bool(enabled),
            created_by=actor_user_id,
        )
    else:
        override.enabled = bool(enabled)

    after_json = _snapshot_rule(rule=override)

    session.add(override)
    _append_rule_change_log(
        session=session,
        company_id=company_id,
        rule_id=override.id,
        actor_user_id=actor_user_id,
        action="rule.toggle_global_enabled",
        changed_fields=["enabled"],
        before_json=before_json,
        after_json=after_json,
    )
    session.commit()
    session.refresh(override)
    RuleEngine.invalidate_cache(company_id)
    return _to_rule_out(rule=override, origin=RuleOrigin.company_override)


def list_personal_rules(
    *,
    session: Session,
    actor_user_id: UUID,
) -> list[PersonalRuleOut]:
    _require_no_active_company_membership(session=session, user_id=actor_user_id)

    global_rules = list(
        session.exec(
            select(Rule)
            .where(Rule.company_id.is_(None))
            .order_by(Rule.priority.desc(), Rule.created_at.desc(), Rule.id.desc())
        ).all()
    )

    overrides = list(
        session.exec(
            select(UserRuleOverride).where(UserRuleOverride.user_id == actor_user_id)
        ).all()
    )
    override_map = {str(r.stable_key): bool(r.enabled) for r in overrides}

    return [
        _to_personal_rule_out(
            rule=r,
            override_enabled=override_map.get(str(r.stable_key)),
            can_toggle_enabled=True,
        )
        for r in global_rules
    ]


def toggle_personal_rule_enabled(
    *,
    session: Session,
    actor_user_id: UUID,
    stable_key: str,
    enabled: bool,
) -> PersonalRuleOut:
    _require_no_active_company_membership(session=session, user_id=actor_user_id)

    normalized_key = _normalize_stable_key(stable_key=stable_key)

    global_rule = session.exec(
        select(Rule)
        .where(Rule.company_id.is_(None))
        .where(Rule.stable_key == normalized_key)
        .order_by(Rule.created_at.desc())
    ).first()
    if not global_rule:
        raise not_found("Global rule not found", field="stable_key")

    override = session.exec(
        select(UserRuleOverride)
        .where(UserRuleOverride.user_id == actor_user_id)
        .where(UserRuleOverride.stable_key == normalized_key)
        .order_by(UserRuleOverride.created_at.desc())
    ).first()

    target_enabled = bool(enabled)
    if target_enabled == bool(global_rule.enabled):
        # same as default => no override row needed
        if override is not None:
            session.delete(override)
    else:
        if override is None:
            override = UserRuleOverride(
                user_id=actor_user_id,
                stable_key=normalized_key,
                enabled=target_enabled,
            )
        else:
            override.enabled = target_enabled
        session.add(override)

    session.commit()
    RuleEngine.invalidate_cache(company_id=None, user_id=actor_user_id)

    refreshed_override = session.exec(
        select(UserRuleOverride)
        .where(UserRuleOverride.user_id == actor_user_id)
        .where(UserRuleOverride.stable_key == normalized_key)
        .order_by(UserRuleOverride.created_at.desc())
    ).first()

    return _to_personal_rule_out(
        rule=global_rule,
        override_enabled=bool(refreshed_override.enabled)
        if refreshed_override
        else None,
        can_toggle_enabled=True,
    )
