from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.common.enums import MemberRole, RuleAction, RuleScope, RuleSeverity, RagMode
from app.common.error_codes import ErrorCode
from app.common.errors import AppError
from app.company.model import Company
from app.core.config import get_settings
from app.llm import generate_text_sync
from app.permissions.core import forbid, not_found
from app.permissions.loaders.conversation import load_company_member_active_or_403
from app.rag.models.context_term import ContextTerm
from app.rule.model import Rule
from app.suggestion.models.rule_suggestion import RuleSuggestion
from app.suggestion.models.rule_suggestion_log import RuleSuggestionLog
from app.suggestion.duplicate_checker import build_duplicate_check
from app.suggestion.schemas import (
    RuleSuggestionApplyIn,
    RuleSuggestionApplyOut,
    RuleSuggestionConfirmIn,
    RuleSuggestionDraftContextTerm,
    RuleSuggestionDraftPayload,
    RuleSuggestionDraftRule,
    RuleSuggestionEditIn,
    RuleSuggestionGenerateOut,
    RuleSuggestionGenerateIn,
    RuleSuggestionLogOut,
    RuleSuggestionOut,
    RuleSuggestionRejectIn,
    SuggestionStatus,
)


SUGGESTION_TTL_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


def _normalize_stable_key(value: str) -> str:
    return _normalize_non_empty(value=value, field="stable_key").lower()


def _normalize_term(value: str) -> str:
    return " ".join(_normalize_non_empty(value=value, field="term").lower().split())


def _normalize_lang(value: str) -> str:
    return _normalize_non_empty(value=value, field="lang").lower()


def _load_company_or_404(*, session: Session, company_id: UUID) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise not_found("Company not found", field="company_id")
    return company


def _require_company_admin(*, session: Session, company_id: UUID, user_id: UUID) -> None:
    member = load_company_member_active_or_403(
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


def _parse_json_object(raw: str) -> dict[str, Any]:
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty_response")
    try:
        return json.loads(s)
    except Exception:
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(s[start : end + 1])
        raise


ENTITY_TYPE_PATTERN = re.compile(r"^[A-Z0-9_]+$")
SIGNAL_OPERATOR_KEYS = {
    "exists",
    "equals",
    "in",
    "contains",
    "any_of",
    "gte",
    "lte",
    "gt",
    "lt",
    "startswith",
    "regex",
}


def _raise_invalid_conditions(*, field: str, reason: str) -> None:
    raise AppError(
        422,
        ErrorCode.VALIDATION_ERROR,
        "Invalid rule conditions",
        details=[{"field": field, "reason": reason}],
    )


def _split_entity_types(*, raw_value: str, field: str) -> list[str]:
    normalized = _normalize_non_empty(value=raw_value, field=field).upper()
    raw_parts = [x.strip() for x in re.split(r"[|,;/]+", normalized) if x.strip()]
    if not raw_parts:
        _raise_invalid_conditions(field=field, reason="empty_entity_type")

    out: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        if not ENTITY_TYPE_PATTERN.match(part):
            _raise_invalid_conditions(field=field, reason="invalid_entity_type_format")
        if part in seen:
            continue
        seen.add(part)
        out.append(part)
    return out


def _normalize_signal_operator_value(*, op: str, value: Any, field: str) -> Any:
    if op == "exists":
        return bool(value)

    if op in {"in", "any_of"}:
        raw_values: list[Any]
        if isinstance(value, list):
            raw_values = value
        elif isinstance(value, str):
            raw_values = [x.strip() for x in re.split(r"[|,;/]+", value) if x.strip()]
        else:
            _raise_invalid_conditions(field=field, reason="operator_requires_list")
        out = [str(x).strip() for x in raw_values if str(x).strip()]
        if not out:
            _raise_invalid_conditions(field=field, reason="operator_list_empty")
        return out

    if op in {"gte", "lte", "gt", "lt"}:
        try:
            return float(value)
        except Exception:
            _raise_invalid_conditions(field=field, reason="operator_requires_number")

    if op in {"contains", "startswith", "regex"}:
        text = str(value or "").strip()
        if not text:
            _raise_invalid_conditions(field=field, reason="operator_requires_non_empty_value")
        return text

    if op == "equals":
        return value

    _raise_invalid_conditions(field=field, reason="unsupported_signal_operator")


def _normalize_signal_leaf(*, signal: Any, field: str) -> dict[str, Any]:
    if not isinstance(signal, dict):
        _raise_invalid_conditions(field=field, reason="signal_must_be_object")

    signal_field = _normalize_non_empty(
        value=str(signal.get("field", "")),
        field=f"{field}.field",
    )
    operators = [k for k in SIGNAL_OPERATOR_KEYS if k in signal]
    if len(operators) != 1:
        _raise_invalid_conditions(
            field=field,
            reason="signal_requires_exactly_one_operator",
        )
    op = operators[0]
    value = _normalize_signal_operator_value(
        op=op,
        value=signal.get(op),
        field=f"{field}.{op}",
    )
    return {"signal": {"field": signal_field, op: value}}


def _normalize_conditions_node(node: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(node, dict):
        _raise_invalid_conditions(field=field, reason="condition_node_not_dict")

    if "any" in node:
        children = node.get("any")
        if not isinstance(children, list):
            _raise_invalid_conditions(field=f"{field}.any", reason="must_be_list")
        if not children:
            _raise_invalid_conditions(field=f"{field}.any", reason="empty_list")
        normalized_children: list[dict[str, Any]] = [
            _normalize_conditions_node(child, field=f"{field}.any[{idx}]")
            for idx, child in enumerate(children)
        ]
        flattened: list[dict[str, Any]] = []
        for child in normalized_children:
            if isinstance(child, dict) and set(child.keys()) == {"any"}:
                inner = child.get("any")
                if isinstance(inner, list):
                    flattened.extend(x for x in inner if isinstance(x, dict))
                    continue
            flattened.append(child)
        if not flattened:
            _raise_invalid_conditions(field=f"{field}.any", reason="empty_after_normalize")
        return {"any": flattened}

    if "all" in node:
        children = node.get("all")
        if not isinstance(children, list):
            _raise_invalid_conditions(field=f"{field}.all", reason="must_be_list")
        if not children:
            _raise_invalid_conditions(field=f"{field}.all", reason="empty_list")
        normalized_children: list[dict[str, Any]] = [
            _normalize_conditions_node(child, field=f"{field}.all[{idx}]")
            for idx, child in enumerate(children)
        ]
        flattened: list[dict[str, Any]] = []
        for child in normalized_children:
            if isinstance(child, dict) and set(child.keys()) == {"all"}:
                inner = child.get("all")
                if isinstance(inner, list):
                    flattened.extend(x for x in inner if isinstance(x, dict))
                    continue
            flattened.append(child)
        if not flattened:
            _raise_invalid_conditions(field=f"{field}.all", reason="empty_after_normalize")
        return {"all": flattened}

    if "not" in node:
        return {
            "not": _normalize_conditions_node(
                node.get("not"),
                field=f"{field}.not",
            )
        }

    if "entity_type" in node:
        entity_types = _split_entity_types(
            raw_value=str(node.get("entity_type", "")),
            field=f"{field}.entity_type",
        )
        leaf_base: dict[str, Any] = {}
        if "min_score" in node:
            try:
                leaf_base["min_score"] = float(node["min_score"])
            except Exception:
                _raise_invalid_conditions(
                    field=f"{field}.min_score",
                    reason="must_be_number",
                )
        if "max_score" in node:
            try:
                leaf_base["max_score"] = float(node["max_score"])
            except Exception:
                _raise_invalid_conditions(
                    field=f"{field}.max_score",
                    reason="must_be_number",
                )
        if "min_score" in leaf_base and "max_score" in leaf_base:
            if float(leaf_base["min_score"]) > float(leaf_base["max_score"]):
                _raise_invalid_conditions(
                    field=field,
                    reason="min_score_gt_max_score",
                )
        if "source" in node:
            source = node.get("source")
            if isinstance(source, str):
                src = source.strip()
                if not src:
                    _raise_invalid_conditions(
                        field=f"{field}.source",
                        reason="empty_source",
                    )
                leaf_base["source"] = src
            elif isinstance(source, list):
                src_list = [str(x).strip() for x in source if str(x).strip()]
                if not src_list:
                    _raise_invalid_conditions(
                        field=f"{field}.source",
                        reason="empty_source",
                    )
                leaf_base["source"] = src_list
            else:
                _raise_invalid_conditions(
                    field=f"{field}.source",
                    reason="invalid_source_type",
                )

        if len(entity_types) == 1:
            return {"entity_type": entity_types[0], **leaf_base}
        return {"any": [{"entity_type": et, **leaf_base} for et in entity_types]}

    if "signal" in node:
        return _normalize_signal_leaf(signal=node.get("signal"), field=f"{field}.signal")

    _raise_invalid_conditions(field=field, reason="unsupported_node")


def _normalize_draft(payload: RuleSuggestionDraftPayload) -> RuleSuggestionDraftPayload:
    rule = payload.rule
    normalized_conditions = _normalize_conditions_node(
        rule.conditions,
        field="draft.rule.conditions",
    )
    action = RuleAction.mask if rule.action == RuleAction.warn else rule.action

    normalized_rule = RuleSuggestionDraftRule(
        stable_key=_normalize_stable_key(rule.stable_key),
        name=_normalize_non_empty(value=rule.name, field="name"),
        description=(rule.description or "").strip() or None,
        scope=rule.scope,
        conditions=normalized_conditions,
        action=action,
        severity=rule.severity,
        priority=int(rule.priority),
        rag_mode=rule.rag_mode,
        enabled=bool(rule.enabled),
    )

    normalized_terms: list[RuleSuggestionDraftContextTerm] = []
    dedupe_terms: set[tuple[str, str, str]] = set()
    for t in payload.context_terms:
        term = _normalize_term(t.term)
        lang = _normalize_lang(t.lang)
        entity_types = _split_entity_types(
            raw_value=t.entity_type,
            field="context_terms.entity_type",
        )
        for entity_type in entity_types:
            key = (entity_type, term, lang)
            if key in dedupe_terms:
                continue
            dedupe_terms.add(key)

            normalized_terms.append(
                RuleSuggestionDraftContextTerm(
                    entity_type=entity_type,
                    term=term,
                    lang=lang,
                    weight=float(t.weight),
                    window_1=max(0, int(t.window_1)),
                    window_2=max(0, int(t.window_2)),
                    enabled=bool(t.enabled),
                )
            )

    return RuleSuggestionDraftPayload(rule=normalized_rule, context_terms=normalized_terms)


def _draft_to_json(payload: RuleSuggestionDraftPayload) -> dict[str, Any]:
    return payload.model_dump(mode="json")


def _dedupe_key(*, company_id: UUID, payload: RuleSuggestionDraftPayload) -> str:
    body = {
        "company_id": str(company_id),
        "type": "rule_with_context",
        "draft": _draft_to_json(payload),
    }
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _snapshot_suggestion(row: RuleSuggestion) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "created_by": str(row.created_by),
        "status": row.status,
        "type": row.type,
        "version": int(row.version),
        "nl_input": row.nl_input,
        "dedupe_key": row.dedupe_key,
        "draft_json": row.draft_json,
        "approve_reason": row.approve_reason,
        "reject_reason": row.reject_reason,
        "applied_result_json": row.applied_result_json,
        "approved_by": str(row.approved_by) if row.approved_by else None,
        "rejected_by": str(row.rejected_by) if row.rejected_by else None,
        "applied_by": str(row.applied_by) if row.applied_by else None,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "rejected_at": row.rejected_at.isoformat() if row.rejected_at else None,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


def _append_log(
    *,
    session: Session,
    suggestion_id: UUID,
    company_id: UUID,
    actor_user_id: UUID,
    action: str,
    reason: str | None = None,
    before_json: dict[str, Any] | None = None,
    after_json: dict[str, Any] | None = None,
) -> None:
    session.add(
        RuleSuggestionLog(
            suggestion_id=suggestion_id,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action=action,
            reason=(reason or "").strip() or None,
            before_json=before_json,
            after_json=after_json,
        )
    )


def _to_out(row: RuleSuggestion) -> RuleSuggestionOut:
    return RuleSuggestionOut(
        id=row.id,
        company_id=row.company_id,
        created_by=row.created_by,
        status=SuggestionStatus(row.status),
        type=row.type,
        version=row.version,
        nl_input=row.nl_input,
        dedupe_key=row.dedupe_key,
        draft=RuleSuggestionDraftPayload.model_validate(row.draft_json),
        applied_result_json=row.applied_result_json,
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_log_out(row: RuleSuggestionLog) -> RuleSuggestionLogOut:
    return RuleSuggestionLogOut(
        id=row.id,
        suggestion_id=row.suggestion_id,
        company_id=row.company_id,
        actor_user_id=row.actor_user_id,
        action=row.action,
        reason=row.reason,
        before_json=row.before_json,
        after_json=row.after_json,
        created_at=row.created_at,
    )


def _expire_if_needed(*, session: Session, row: RuleSuggestion) -> RuleSuggestion:
    if row.status in {
        SuggestionStatus.applied.value,
        SuggestionStatus.rejected.value,
        SuggestionStatus.expired.value,
        SuggestionStatus.failed.value,
    }:
        return row
    if row.expires_at and row.expires_at <= _utcnow():
        row.status = SuggestionStatus.expired.value
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def _find_active_duplicate(
    *,
    session: Session,
    company_id: UUID,
    dedupe_key: str,
    exclude_suggestion_id: UUID | None = None,
) -> RuleSuggestion | None:
    stmt = (
        select(RuleSuggestion)
        .where(RuleSuggestion.company_id == company_id)
        .where(RuleSuggestion.dedupe_key == dedupe_key)
        .where(
            RuleSuggestion.status.in_(
                [SuggestionStatus.draft.value, SuggestionStatus.approved.value]
            )
        )
        .order_by(RuleSuggestion.created_at.desc())
    )
    rows = list(session.exec(stmt).all())
    for row in rows:
        if exclude_suggestion_id and row.id == exclude_suggestion_id:
            continue
        row = _expire_if_needed(session=session, row=row)
        if row.status in {SuggestionStatus.draft.value, SuggestionStatus.approved.value}:
            return row
    return None


def _assert_expected_version(
    *,
    current_version: int,
    expected_version: int | None,
) -> None:
    if expected_version is None:
        return
    if int(expected_version) != int(current_version):
        raise AppError(
            409,
            ErrorCode.CONFLICT,
            "Suggestion version mismatch",
            details=[{"field": "expected_version", "reason": "stale_version"}],
        )


def _has_any(text: str, keys: list[str]) -> bool:
    t = text.lower()
    return any(k in t for k in keys)


def _action_hint_from_prompt(prompt: str) -> RuleAction:
    p = prompt.lower()
    if _has_any(p, ["allow", "cho phep", "cho phép"]):
        return RuleAction.allow
    if _has_any(p, ["mask", "che", "ẩn", "an"]):
        return RuleAction.mask
    if _has_any(p, ["block", "chan", "chặn"]):
        return RuleAction.block
    return RuleAction.mask


def _contains_entity_leaf(conditions: Any) -> bool:
    if isinstance(conditions, dict):
        if "entity_type" in conditions:
            return True
        return any(_contains_entity_leaf(v) for v in conditions.values())
    if isinstance(conditions, list):
        return any(_contains_entity_leaf(x) for x in conditions)
    return False


def _build_persona_signal_draft(
    *,
    prompt: str,
    persona: str,
    keywords: list[str],
    action: RuleAction,
    stable_suffix: str,
) -> RuleSuggestionDraftPayload:
    stable_key = f"company.custom.suggested.{stable_suffix}"
    rule_name = (
        f"Suggested office context {action.value}"
        if persona == "office"
        else f"Suggested dev context {action.value}"
    )
    priority = 105 if action == RuleAction.block else 95
    risk_threshold = 0.10 if persona == "office" else 0.15
    keyword_values = keywords[:6] or ["context"]

    rule = RuleSuggestionDraftRule(
        stable_key=stable_key,
        name=rule_name,
        description=f"Auto-generated from prompt: {prompt[:180]}",
        scope=RuleScope.prompt,
        conditions={
            "all": [
                {"signal": {"field": "persona", "equals": persona}},
                {"signal": {"field": "risk_boost", "gte": risk_threshold}},
                {"signal": {"field": "context_keywords", "any_of": keyword_values}},
            ]
        },
        action=action,
        severity=RuleSeverity.medium if action != RuleAction.block else RuleSeverity.high,
        priority=priority,
        rag_mode=RagMode.off,
        enabled=True,
    )

    ctx_entity = "PERSONA_OFFICE" if persona == "office" else "PERSONA_DEV"
    ctx_terms = [
        RuleSuggestionDraftContextTerm(entity_type=ctx_entity, term=k, lang="vi")
        for k in keyword_values[:3]
    ]
    return RuleSuggestionDraftPayload(rule=rule, context_terms=ctx_terms)


def _fallback_generate(prompt: str) -> RuleSuggestionDraftPayload:
    p = prompt.lower()
    action = _action_hint_from_prompt(prompt)
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]

    office_hr_keys = [
        "luong",
        "lương",
        "hop dong",
        "hợp đồng",
        "nhan su",
        "nhân sự",
        "hr",
    ]
    dev_infra_keys = ["docker", "kubernetes", "github", "helm", "ci cd", "devops"]

    if _has_any(p, office_hr_keys):
        matched = [k for k in office_hr_keys if k in p][:4]
        return _build_persona_signal_draft(
            prompt=prompt,
            persona="office",
            keywords=matched or ["nhan su", "hop dong", "luong"],
            action=action,
            stable_suffix=h,
        )

    if _has_any(p, dev_infra_keys):
        matched = [k for k in dev_infra_keys if k in p][:4]
        return _build_persona_signal_draft(
            prompt=prompt,
            persona="dev",
            keywords=matched or ["docker", "kubernetes", "github"],
            action=action,
            stable_suffix=h,
        )

    if _has_any(p, ["cccd", "cmnd", "can cuoc", "căn cước"]):
        entity_type = "CCCD"
    elif _has_any(p, ["tax", "mst", "ma so thue", "mã số thuế"]):
        entity_type = "TAX_ID"
    elif _has_any(p, ["phone", "sdt", "so dien thoai", "số điện thoại", "hotline"]):
        entity_type = "PHONE"
    else:
        entity_type = "TAX_ID"

    stable_key = f"company.custom.suggested.{h}"
    return RuleSuggestionDraftPayload(
        rule=RuleSuggestionDraftRule(
            stable_key=stable_key,
            name=f"Suggested {entity_type} {action.value}",
            description=f"Auto-generated from prompt: {prompt[:180]}",
            scope=RuleScope.prompt,
            conditions={"any": [{"entity_type": entity_type}]},
            action=action,
            severity=RuleSeverity.medium,
            priority=120,
            rag_mode=RagMode.off,
            enabled=True,
        ),
        context_terms=[],
    )


def _align_draft_with_prompt(
    prompt: str, draft: RuleSuggestionDraftPayload
) -> RuleSuggestionDraftPayload:
    p = prompt.lower()
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]

    if _has_any(p, ["luong", "lương", "hop dong", "hợp đồng", "nhan su", "nhân sự", "hr"]):
        if _contains_entity_leaf(draft.rule.conditions):
            return _build_persona_signal_draft(
                prompt=prompt,
                persona="office",
                keywords=["nhan su", "hop dong", "luong"],
                action=draft.rule.action,
                stable_suffix=h,
            )

    if _has_any(p, ["docker", "kubernetes", "github", "helm", "devops"]):
        if _contains_entity_leaf(draft.rule.conditions):
            return _build_persona_signal_draft(
                prompt=prompt,
                persona="dev",
                keywords=["docker", "kubernetes", "github"],
                action=draft.rule.action,
                stable_suffix=h,
            )

    return draft


def _generate_with_llm(prompt: str) -> RuleSuggestionDraftPayload:
    system_prompt = """
You generate security rule drafts in strict JSON.
Output ONLY one JSON object with this schema:
{
  "rule": {
    "stable_key": "string",
    "name": "string",
    "description": "string|null",
    "scope": "prompt|chat|file|api",
    "conditions": {"all":[{"signal":{"field":"persona","equals":"dev|office"}}]} OR {"any":[{"entity_type":"PHONE|CCCD|TAX_ID|EMAIL|CREDIT_CARD"}]},
    "action": "allow|mask|block",
    "severity": "low|medium|high",
    "priority": 0,
    "rag_mode": "off|explain|verify",
    "enabled": true
  },
  "context_terms": [
    {
      "entity_type":"PHONE|CCCD|TAX_ID|PERSONA_*",
      "term":"string",
      "lang":"vi|en",
      "weight":1.0,
      "window_1":60,
      "window_2":20,
      "enabled":true
    }
  ]
}
Return valid JSON only.
""".strip()

    llm_out = generate_text_sync(
        prompt=f"User input:\n{prompt}",
        system_prompt=system_prompt,
        provider=get_settings().non_embedding_llm_provider,
    )
    raw = llm_out.text
    obj = _parse_json_object(raw)
    return RuleSuggestionDraftPayload.model_validate(obj)


def _generate_draft_from_prompt(prompt: str) -> RuleSuggestionDraftPayload:
    normalized_prompt = _normalize_non_empty(value=prompt, field="prompt")
    try:
        draft = _generate_with_llm(normalized_prompt)
    except Exception:
        draft = _fallback_generate(normalized_prompt)
    draft = _align_draft_with_prompt(normalized_prompt, draft)
    return _normalize_draft(draft)


def _load_suggestion_or_404(
    *, session: Session, company_id: UUID, suggestion_id: UUID
) -> RuleSuggestion:
    row = session.get(RuleSuggestion, suggestion_id)
    if not row or row.company_id != company_id:
        raise not_found("Suggestion not found", field="suggestion_id")
    return _expire_if_needed(session=session, row=row)


def generate_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionGenerateIn,
) -> RuleSuggestionGenerateOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    draft = _generate_draft_from_prompt(payload.prompt)
    duplicate_check = build_duplicate_check(
        session=session,
        company_id=company_id,
        draft_rule=draft.rule,
    )
    key = _dedupe_key(company_id=company_id, payload=draft)

    existed = _find_active_duplicate(
        session=session,
        company_id=company_id,
        dedupe_key=key,
    )
    if existed:
        _append_log(
            session=session,
            suggestion_id=existed.id,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="suggestion.generate.duplicate_hit",
            reason="dedupe_key_matched_active_suggestion",
            before_json=None,
            after_json=_snapshot_suggestion(existed),
        )
        session.commit()
        session.refresh(existed)
        return RuleSuggestionGenerateOut(
            **_to_out(existed).model_dump(),
            duplicate_check=duplicate_check,
        )

    row = RuleSuggestion(
        company_id=company_id,
        created_by=actor_user_id,
        status=SuggestionStatus.draft.value,
        type="rule_with_context",
        version=1,
        nl_input=_normalize_non_empty(value=payload.prompt, field="prompt"),
        draft_json=_draft_to_json(draft),
        dedupe_key=key,
        expires_at=_utcnow() + timedelta(days=SUGGESTION_TTL_DAYS),
    )
    session.add(row)
    session.flush()
    _append_log(
        session=session,
        suggestion_id=row.id,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="suggestion.create",
        before_json=None,
        after_json=_snapshot_suggestion(row),
    )
    session.commit()
    session.refresh(row)
    return RuleSuggestionGenerateOut(
        **_to_out(row).model_dump(),
        duplicate_check=duplicate_check,
    )


def list_rule_suggestions(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    status: SuggestionStatus | None,
    limit: int,
) -> list[RuleSuggestionOut]:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    safe_limit = max(1, min(int(limit), 200))
    stmt = (
        select(RuleSuggestion)
        .where(RuleSuggestion.company_id == company_id)
        .order_by(RuleSuggestion.created_at.desc())
        .limit(safe_limit)
    )
    if status is not None:
        stmt = stmt.where(RuleSuggestion.status == status.value)
    rows = list(session.exec(stmt).all())
    out: list[RuleSuggestionOut] = []
    for row in rows:
        row = _expire_if_needed(session=session, row=row)
        out.append(_to_out(row))
    return out


def get_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
) -> RuleSuggestionOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)
    row = _load_suggestion_or_404(
        session=session, company_id=company_id, suggestion_id=suggestion_id
    )
    return _to_out(row)


def list_rule_suggestion_logs(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
    limit: int,
) -> list[RuleSuggestionLogOut]:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)
    _load_suggestion_or_404(session=session, company_id=company_id, suggestion_id=suggestion_id)

    safe_limit = max(1, min(int(limit), 200))
    rows = list(
        session.exec(
            select(RuleSuggestionLog)
            .where(RuleSuggestionLog.suggestion_id == suggestion_id)
            .order_by(RuleSuggestionLog.created_at.desc())
            .limit(safe_limit)
        ).all()
    )
    return [_to_log_out(r) for r in rows]


def edit_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionEditIn,
) -> RuleSuggestionOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)

    row = _load_suggestion_or_404(
        session=session, company_id=company_id, suggestion_id=suggestion_id
    )
    if row.status != SuggestionStatus.draft.value:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Only draft suggestion can be edited",
            details=[{"field": "status", "reason": "not_draft"}],
        )
    _assert_expected_version(
        current_version=int(row.version),
        expected_version=payload.expected_version,
    )

    normalized = _normalize_draft(payload.draft)
    key = _dedupe_key(company_id=company_id, payload=normalized)
    existed = _find_active_duplicate(
        session=session,
        company_id=company_id,
        dedupe_key=key,
        exclude_suggestion_id=row.id,
    )
    if existed:
        raise AppError.conflict(
            ErrorCode.CONFLICT,
            "Duplicate active suggestion exists",
            field="draft",
        )

    before_json = _snapshot_suggestion(row)
    row.draft_json = _draft_to_json(normalized)
    row.dedupe_key = key
    row.version = int(row.version) + 1
    session.add(row)
    _append_log(
        session=session,
        suggestion_id=row.id,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="suggestion.edit",
        before_json=before_json,
        after_json=_snapshot_suggestion(row),
    )
    session.commit()
    session.refresh(row)
    return _to_out(row)


def confirm_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionConfirmIn,
) -> RuleSuggestionOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)
    row = _load_suggestion_or_404(
        session=session, company_id=company_id, suggestion_id=suggestion_id
    )
    if row.status != SuggestionStatus.draft.value:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Only draft suggestion can be confirmed",
            details=[{"field": "status", "reason": "not_draft"}],
        )
    _assert_expected_version(
        current_version=int(row.version),
        expected_version=payload.expected_version,
    )

    before_json = _snapshot_suggestion(row)
    row.status = SuggestionStatus.approved.value
    row.version = int(row.version) + 1
    row.approved_by = actor_user_id
    row.approved_at = _utcnow()
    row.approve_reason = (payload.reason or "").strip() or None
    session.add(row)
    _append_log(
        session=session,
        suggestion_id=row.id,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="suggestion.confirm",
        reason=row.approve_reason,
        before_json=before_json,
        after_json=_snapshot_suggestion(row),
    )
    session.commit()
    session.refresh(row)
    return _to_out(row)


def reject_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionRejectIn,
) -> RuleSuggestionOut:
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)
    row = _load_suggestion_or_404(
        session=session, company_id=company_id, suggestion_id=suggestion_id
    )
    if row.status not in {SuggestionStatus.draft.value, SuggestionStatus.approved.value}:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Suggestion cannot be rejected in current status",
            details=[{"field": "status", "reason": "invalid_status"}],
        )
    _assert_expected_version(
        current_version=int(row.version),
        expected_version=payload.expected_version,
    )

    before_json = _snapshot_suggestion(row)
    row.status = SuggestionStatus.rejected.value
    row.version = int(row.version) + 1
    row.rejected_by = actor_user_id
    row.rejected_at = _utcnow()
    row.reject_reason = (payload.reason or "").strip() or None
    session.add(row)
    _append_log(
        session=session,
        suggestion_id=row.id,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="suggestion.reject",
        reason=row.reject_reason,
        before_json=before_json,
        after_json=_snapshot_suggestion(row),
    )
    session.commit()
    session.refresh(row)
    return _to_out(row)


def _apply_rule_draft(
    *,
    session: Session,
    company_id: UUID,
    actor_user_id: UUID,
    rule_draft: RuleSuggestionDraftRule,
) -> Rule:
    global_row = session.exec(
        select(Rule)
        .where(Rule.company_id.is_(None))
        .where(Rule.stable_key == rule_draft.stable_key)
    ).first()
    if global_row:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "stable_key is reserved by global rule",
            details=[{"field": "draft.rule.stable_key", "reason": "global_rule_key_reserved"}],
        )

    row = session.exec(
        select(Rule)
        .where(Rule.company_id == company_id)
        .where(Rule.stable_key == rule_draft.stable_key)
        .order_by(Rule.created_at.desc())
    ).first()
    if row is None:
        row = Rule(
            company_id=company_id,
            stable_key=rule_draft.stable_key,
            name=rule_draft.name,
            description=rule_draft.description,
            scope=rule_draft.scope,
            conditions=rule_draft.conditions,
            conditions_version=1,
            action=rule_draft.action,
            severity=rule_draft.severity,
            priority=rule_draft.priority,
            rag_mode=rule_draft.rag_mode,
            enabled=rule_draft.enabled,
            created_by=actor_user_id,
        )
        session.add(row)
        session.flush()
        return row

    row.name = rule_draft.name
    row.description = rule_draft.description
    row.scope = rule_draft.scope
    row.conditions = rule_draft.conditions
    row.conditions_version = int(row.conditions_version or 1) + 1
    row.action = rule_draft.action
    row.severity = rule_draft.severity
    row.priority = int(rule_draft.priority)
    row.rag_mode = rule_draft.rag_mode
    row.enabled = bool(rule_draft.enabled)
    session.add(row)
    session.flush()
    return row


def _apply_context_terms(
    *,
    session: Session,
    company_id: UUID,
    terms: list[RuleSuggestionDraftContextTerm],
) -> list[UUID]:
    out_ids: list[UUID] = []
    for t in terms:
        row = session.exec(
            select(ContextTerm)
            .where(ContextTerm.company_id == company_id)
            .where(ContextTerm.entity_type == t.entity_type)
            .where(ContextTerm.term == t.term)
            .where(ContextTerm.lang == t.lang)
            .order_by(ContextTerm.created_at.desc())
        ).first()
        if row is None:
            row = ContextTerm(
                company_id=company_id,
                entity_type=t.entity_type,
                term=t.term,
                lang=t.lang,
                weight=t.weight,
                window_1=t.window_1,
                window_2=t.window_2,
                enabled=t.enabled,
            )
        else:
            row.weight = t.weight
            row.window_1 = t.window_1
            row.window_2 = t.window_2
            row.enabled = t.enabled

        session.add(row)
        session.flush()
        out_ids.append(row.id)
    return out_ids


def apply_rule_suggestion(
    *,
    session: Session,
    company_id: UUID,
    suggestion_id: UUID,
    actor_user_id: UUID,
    payload: RuleSuggestionApplyIn | None = None,
) -> RuleSuggestionApplyOut:
    payload = payload or RuleSuggestionApplyIn()
    _load_company_or_404(session=session, company_id=company_id)
    _require_company_admin(session=session, company_id=company_id, user_id=actor_user_id)
    row = _load_suggestion_or_404(
        session=session, company_id=company_id, suggestion_id=suggestion_id
    )
    _assert_expected_version(
        current_version=int(row.version),
        expected_version=payload.expected_version,
    )
    if row.status == SuggestionStatus.applied.value:
        result = row.applied_result_json or {}
        rule_id = str(result.get("rule_id") or "").strip()
        if not rule_id:
            raise AppError(
                409,
                ErrorCode.CONFLICT,
                "Suggestion was marked applied without result payload",
                details=[{"field": "applied_result_json", "reason": "missing_rule_id"}],
            )
        return RuleSuggestionApplyOut(
            rule_id=UUID(rule_id),
            context_term_ids=[UUID(str(x)) for x in list(result.get("context_term_ids") or [])],
        )
    if row.status != SuggestionStatus.approved.value:
        raise AppError(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Only approved suggestion can be applied",
            details=[{"field": "status", "reason": "not_approved"}],
        )

    draft = _normalize_draft(RuleSuggestionDraftPayload.model_validate(row.draft_json))
    before_json = _snapshot_suggestion(row)

    try:
        rule_row = _apply_rule_draft(
            session=session,
            company_id=company_id,
            actor_user_id=actor_user_id,
            rule_draft=draft.rule,
        )
        context_term_ids = _apply_context_terms(
            session=session,
            company_id=company_id,
            terms=draft.context_terms,
        )
        row.status = SuggestionStatus.applied.value
        row.version = int(row.version) + 1
        row.applied_by = actor_user_id
        row.applied_at = _utcnow()
        row.applied_result_json = {
            "rule_id": str(rule_row.id),
            "context_term_ids": [str(x) for x in context_term_ids],
        }
        session.add(row)
        _append_log(
            session=session,
            suggestion_id=row.id,
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="suggestion.apply",
            before_json=before_json,
            after_json=_snapshot_suggestion(row),
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return RuleSuggestionApplyOut(
        rule_id=rule_row.id,
        context_term_ids=context_term_ids,
    )
