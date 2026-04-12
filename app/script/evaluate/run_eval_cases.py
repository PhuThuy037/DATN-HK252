from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

from sqlalchemy.exc import OperationalError
import sqlalchemy as sa
from sqlmodel import Session, select

from app.auth.model import User
from app.common.enums import (
    MemberRole,
    MemberStatus,
    RuleScope,
    SystemRole,
    UserStatus,
)
from app.company.model import Company
from app.company_member.model import CompanyMember
from app.core.config import get_settings
from app.db.engine import engine
from app.decision.scan_engine_local import ScanEngineLocal
from app.decision.serializers import rulematch_to_dict
from app.masking.service import MaskService
from app.rule.model import Rule
from app.suggestion.literal_detector import score_identifier_token


DEFAULT_INPUT_PATH = SCRIPT_DIR / "evaluate-test-case" / "eval_cases.json"
DEFAULT_RESULTS_PATH = SCRIPT_DIR / "summary" / "eval_results.json"
DEFAULT_SUMMARY_PATH = SCRIPT_DIR / "summary" / "eval_summary.json"

_MASK_SERVICE = MaskService()
_CODE_LIKE_TERM_RE = re.compile(r"[A-Za-z0-9]{2,}(?:[-_][A-Za-z0-9]{1,}){1,}")
_LITERAL_SEPARATORS = "-_./:#@$"
_KNOWN_PII_FORCE_TERM_BLOCKLIST = {
    "cccd",
    "cmnd",
    "can cuoc",
    "can cuoc cong dan",
    "email",
    "mail",
    "e-mail",
    "phone",
    "sdt",
    "so dien thoai",
    "dien thoai",
    "hotline",
    "mst",
    "ma so thue",
    "tax id",
    "tax code",
    "taxpayer id",
    "tin",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run evaluation cases against the current scan/mask/block runtime.",
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="Path to eval cases JSON. Default: evaluate-test-case/eval_cases.json",
    )
    parser.add_argument(
        "--results-out",
        default=str(DEFAULT_RESULTS_PATH),
        help="Path to write detailed results JSON. Default: summary/eval_results.json",
    )
    parser.add_argument(
        "--summary-out",
        default=str(DEFAULT_SUMMARY_PATH),
        help="Path to write summary JSON. Default: summary/eval_summary.json",
    )
    parser.add_argument(
        "--rule-set-id",
        default=os.getenv("EVAL_RULE_SET_ID", "").strip() or None,
        help="Rule set UUID to evaluate against. Can also be provided via EVAL_RULE_SET_ID.",
    )
    return parser.parse_args()


def _build_scan_engine() -> ScanEngineLocal:
    return ScanEngineLocal(context_yaml_path="app/config/context_base.yaml")


def _load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Input JSON must be an array of cases.")
    return payload


def _serialize_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_serialize_json(payload) + "\n", encoding="utf-8")


def _normalize_action(value: Any) -> str:
    return str(value or "").strip().lower()


def _fold_text(value: str) -> str:
    raw = str(value or "").lower().replace("\u0111", "d")
    normalized = unicodedata.normalize("NFKD", raw)
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", no_marks).strip()


def _extract_code_like_mask_terms(scan_payload: dict[str, Any]) -> list[str]:
    signals = scan_payload.get("signals") if isinstance(scan_payload, dict) else None
    if not isinstance(signals, dict):
        return []
    context_keywords = signals.get("context_keywords")
    if not isinstance(context_keywords, list):
        return []

    out: list[str] = []
    seen: set[str] = set()
    for value in context_keywords:
        term = str(value or "").strip()
        if not term:
            continue
        if _CODE_LIKE_TERM_RE.search(term) is None:
            continue
        lowered = term.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(term)
    return out


def _should_force_mask_term(term: str) -> bool:
    raw = str(term or "").strip()
    if not raw or len(raw) < 4:
        return False
    folded = _fold_text(raw)
    if not folded:
        return False
    if folded in _KNOWN_PII_FORCE_TERM_BLOCKLIST:
        return False
    if re.fullmatch(r"\[[A-Z0-9_]+\]", raw):
        return False

    score = score_identifier_token(raw)
    if score >= 0.45:
        return True

    has_separator = any(ch in _LITERAL_SEPARATORS for ch in raw)
    if has_separator and score >= 0.32:
        return True
    return False


def _extract_context_keyword_terms_from_conditions(node: object) -> set[str]:
    out: set[str] = set()
    if isinstance(node, dict):
        signal = node.get("signal")
        if isinstance(signal, dict):
            field = str(signal.get("field") or "").strip().lower()
            if field == "context_keywords":
                for op in ("equals", "contains", "startswith", "regex"):
                    if op in signal:
                        value = str(signal.get(op) or "").strip()
                        if value:
                            out.add(value)
                for op in ("in", "any_of"):
                    raw = signal.get(op)
                    if isinstance(raw, list):
                        for item in raw:
                            value = str(item or "").strip()
                            if value:
                                out.add(value)
                    elif isinstance(raw, str):
                        value = raw.strip()
                        if value:
                            out.add(value)
        for value in node.values():
            out.update(_extract_context_keyword_terms_from_conditions(value))
        return out

    if isinstance(node, list):
        for item in node:
            out.update(_extract_context_keyword_terms_from_conditions(item))
    return out


def _extract_signal_terms_from_conditions(node: object, field_name: str) -> set[str]:
    out: set[str] = set()
    target_field = str(field_name or "").strip().lower()
    if not target_field:
        return out

    if isinstance(node, dict):
        signal = node.get("signal")
        if isinstance(signal, dict):
            field = str(signal.get("field") or "").strip().lower()
            if field == target_field:
                for op in ("equals", "contains", "startswith", "regex"):
                    if op in signal:
                        value = str(signal.get(op) or "").strip()
                        if value:
                            out.add(value)
                for op in ("in", "any_of", "all_of"):
                    raw = signal.get(op)
                    if isinstance(raw, list):
                        for item in raw:
                            value = str(item or "").strip()
                            if value:
                                out.add(value)
                    elif isinstance(raw, str):
                        value = raw.strip()
                        if value:
                            out.add(value)
        for value in node.values():
            out.update(_extract_signal_terms_from_conditions(value, target_field))
        return out

    if isinstance(node, list):
        for item in node:
            out.update(_extract_signal_terms_from_conditions(item, target_field))
    return out


def _extract_forced_mask_terms_from_matches(
    *,
    session: Session,
    matches: list[object],
    limit: int = 40,
) -> list[str]:
    rule_ids: list[UUID] = []
    for row in matches:
        rule_id = getattr(row, "rule_id", None)
        if isinstance(rule_id, UUID):
            rule_ids.append(rule_id)
    if not rule_ids:
        return []

    rows = list(session.exec(select(Rule.conditions).where(Rule.id.in_(rule_ids))).all())
    seen: set[str] = set()
    out: list[str] = []
    safe_limit = max(1, int(limit))

    for conditions in rows:
        for term in _extract_context_keyword_terms_from_conditions(conditions):
            text = str(term).strip()
            folded = _fold_text(text)
            if not folded or folded in seen:
                continue
            if not _should_force_mask_term(text):
                continue
            seen.add(folded)
            out.append(text)
            if len(out) >= safe_limit:
                return out
    return out


def _mask_text_for_scan(
    *,
    session: Session,
    text: str,
    final_action: str,
    scan_out: dict[str, Any],
) -> str | None:
    if final_action != "mask":
        return None

    entities = list(scan_out.get("entities") or [])
    matches = list(scan_out.get("matches") or [])
    return _MASK_SERVICE.mask(
        text,
        entities,
        extra_terms=_extract_code_like_mask_terms(scan_out),
        force_terms=_extract_forced_mask_terms_from_matches(
            session=session,
            matches=matches,
        ),
    )


def _evaluate_mask(
    *,
    expected_mask: dict[str, Any] | None,
    actual_masked_text: str | None,
) -> bool | None:
    if expected_mask is None:
        return None

    text = actual_masked_text or ""
    contains = expected_mask.get("contains") or []
    not_contains = expected_mask.get("not_contains") or []

    if not isinstance(contains, list) or not isinstance(not_contains, list):
        raise ValueError("expected_mask.contains and expected_mask.not_contains must be arrays.")

    contains_ok = all(str(item) in text for item in contains)
    not_contains_ok = all(str(item) not in text for item in not_contains)
    return contains_ok and not_contains_ok


def _truncate_text(text: str, limit: int = 120) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return f"{value[: max(1, limit - 3)].rstrip()}..."


def _format_percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0%"
    pct = (float(numerator) / float(denominator)) * 100.0
    if abs(pct - round(pct)) < 0.05:
        return f"{int(round(pct))}%"
    return f"{pct:.1f}%"


def _first_matched_rule(matched_rules: list[dict[str, Any]]) -> str | None:
    for row in matched_rules:
        stable_key = str(row.get("stable_key") or "").strip()
        if stable_key:
            return stable_key
        name = str(row.get("name") or "").strip()
        if name:
            return name
    return None


def _resolve_fail_reason(
    *,
    action_pass: bool,
    mask_pass: bool | None,
    expected_action: str,
    actual_action: str,
    matched_rules: list[dict[str, Any]],
) -> str | None:
    mask_failed = mask_pass is False
    if action_pass and not mask_failed:
        return None
    if not matched_rules:
        return "no_rule_matched"
    if not action_pass and mask_failed:
        return "action_and_mask"
    if expected_action == "mask" and actual_action != "mask":
        return "mask_missing"
    if mask_failed:
        return "mask_missing"
    if not action_pass:
        return "wrong_action"
    return None


def _case_passed(*, action_pass: bool, mask_pass: bool | None) -> bool:
    return action_pass and (mask_pass is None or mask_pass is True)


def _summarize_breakdown(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        bucket = str(item.get(key) or "unknown")
        grouped.setdefault(bucket, []).append(item)

    out: dict[str, dict[str, Any]] = {}
    for bucket, rows in sorted(grouped.items()):
        total = len(rows)
        passed = sum(1 for row in rows if bool(row.get("case_pass")))
        failed = total - passed
        out[bucket] = {
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": failed,
            "pass_rate": round((passed / total), 4) if total else 0.0,
        }
    return out


def _format_result_case(raw: dict[str, Any]) -> dict[str, Any]:
    case_pass = bool(raw.get("case_pass"))
    matched_rules = list(raw.get("matched_rules") or [])
    return {
        "id": raw.get("id"),
        "group": raw.get("group"),
        "status": "PASS" if case_pass else "FAIL",
        "input": _truncate_text(str(raw.get("input") or ""), limit=120),
        "expected": raw.get("expected_action"),
        "actual": raw.get("actual_action"),
        "reason": raw.get("fail_reason"),
        "matched_rule": _first_matched_rule(matched_rules),
    }


def _print_console_summary(*, summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    print("=== SUMMARY ===")
    print(
        f"Total: {summary['total']} | Passed: {summary['passed']} | "
        f"Failed: {summary['failed']} | Pass rate: {summary['pass_rate']}"
    )
    print()

    print("=== TOP FAIL GROUP ===")
    top_groups = list(summary.get("top_fail_groups") or [])[:3]
    if not top_groups:
        print("(none)")
    else:
        for row in top_groups:
            print(f"{row['group']} -> {row['failed']} fail")
    print()

    print("=== FAILED CASES ===")
    failed_rows = [row for row in results if row.get("status") == "FAIL"]
    if not failed_rows:
        print("(none)")
        return

    for idx, row in enumerate(failed_rows):
        print(f"[{row['group']}] {row['id']}")
        print(f"expected={row['expected']} actual={row['actual']}")
        print(f"reason={row['reason']}")
        if idx < len(failed_rows) - 1:
            print()


def _list_rule_sets(session: Session) -> list[tuple[UUID, str]]:
    rows = session.exec(
        select(Company.id, Company.name).order_by(Company.created_at.desc(), Company.id.desc())
    ).all()
    return [(row[0], row[1]) for row in rows]


def _resolve_default_admin_rule_set_id(session: Session) -> UUID | None:
    settings = get_settings()
    admin_email = str(settings.default_ruleset_admin_email or "").strip().lower()
    if not admin_email:
        return None

    admin_user = session.exec(
        select(User)
        .where(sa.func.lower(User.email) == admin_email)
        .where(User.status == UserStatus.active)
        .limit(1)
    ).first()
    if admin_user is None or admin_user.role != SystemRole.admin:
        return None

    membership = session.exec(
        select(CompanyMember)
        .where(CompanyMember.user_id == admin_user.id)
        .where(CompanyMember.status == MemberStatus.active)
        .where(CompanyMember.role == MemberRole.company_admin)
        .order_by(CompanyMember.joined_at.desc())
        .limit(1)
    ).first()
    if membership is None:
        return None

    company = session.get(Company, membership.company_id)
    if company is None:
        return None
    return company.id


def _resolve_rule_set_id(session: Session, raw_rule_set_id: str | None) -> UUID:
    candidate = str(raw_rule_set_id or "").strip()
    if candidate:
        return UUID(candidate)

    default_admin_rule_set_id = _resolve_default_admin_rule_set_id(session)
    if default_admin_rule_set_id is not None:
        return default_admin_rule_set_id

    rows = _list_rule_sets(session)
    if len(rows) == 1:
        return rows[0][0]

    if not rows:
        raise RuntimeError(
            "No rule set found in database. Create/seed a rule set first, then rerun with --rule-set-id."
        )

    available = "\n".join(f"- {rule_set_id} | {name}" for rule_set_id, name in rows[:20])
    raise RuntimeError(
        "Multiple rule sets found. Pass --rule-set-id (or EVAL_RULE_SET_ID) to choose one.\n"
        f"Available rule sets:\n{available}"
    )


async def _run_case(
    *,
    session: Session,
    case: dict[str, Any],
    rule_set_id: UUID,
    scan_engine: ScanEngineLocal,
) -> dict[str, Any]:
    case_id = str(case.get("id") or "").strip()
    group = str(case.get("group") or "").strip()
    description = str(case.get("description") or "").strip()
    text = str(case.get("input") or "")
    expected_action = _normalize_action(case.get("expected_action"))
    expected_mask = case.get("expected_mask")

    scan_out = await scan_engine.scan(
        session=session,
        text=text,
        company_id=rule_set_id,
        user_id=None,
        scope=RuleScope.prompt,
    )
    actual_action = _normalize_action(getattr(scan_out.get("final_action"), "value", scan_out.get("final_action")))
    actual_masked_text = _mask_text_for_scan(
        session=session,
        text=text,
        final_action=actual_action,
        scan_out=scan_out,
    )
    matched_rules = [rulematch_to_dict(row) for row in list(scan_out.get("matches") or [])]
    action_pass = expected_action == actual_action
    mask_pass = _evaluate_mask(
        expected_mask=expected_mask if isinstance(expected_mask, dict) else None,
        actual_masked_text=actual_masked_text,
    )
    fail_reason = _resolve_fail_reason(
        action_pass=action_pass,
        mask_pass=mask_pass,
        expected_action=expected_action,
        actual_action=actual_action,
        matched_rules=matched_rules,
    )

    result = {
        "id": case_id,
        "group": group,
        "description": description,
        "input": text,
        "expected_action": expected_action,
        "actual_action": actual_action,
        "action_pass": action_pass,
        "expected_mask": expected_mask if isinstance(expected_mask, dict) else None,
        "actual_masked_text": actual_masked_text,
        "mask_pass": mask_pass,
        "fail_reason": fail_reason,
        "matched_rules": matched_rules,
        "signals": dict(scan_out.get("signals") or {}),
        "latency_ms": scan_out.get("latency_ms"),
    }
    result["case_pass"] = _case_passed(action_pass=action_pass, mask_pass=mask_pass)
    return result


async def _evaluate_cases(
    *,
    cases: list[dict[str, Any]],
    rule_set_id: UUID,
    scan_engine: ScanEngineLocal,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with Session(engine) as session:
        for case in cases:
            results.append(
                await _run_case(
                    session=session,
                    case=case,
                    rule_set_id=rule_set_id,
                    scan_engine=scan_engine,
                )
            )
    return results


def _build_summary(
    *,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for row in results if bool(row.get("case_pass")))
    failed = total - passed
    fail_groups: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        grouped.setdefault(str(row.get("group") or "unknown"), []).append(row)

    for group, rows in grouped.items():
        failed_count = sum(1 for row in rows if not bool(row.get("case_pass")))
        if failed_count <= 0:
            continue
        passed_count = len(rows) - failed_count
        fail_groups.append(
            {
                "group": group,
                "failed": failed_count,
                "pass_rate": _format_percent(passed_count, len(rows)),
            }
        )
    fail_groups.sort(key=lambda row: (-int(row["failed"]), str(row["group"])))

    fail_reason_counter = Counter(
        str(row.get("fail_reason") or "")
        for row in results
        if not bool(row.get("case_pass")) and str(row.get("fail_reason") or "").strip()
    )

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": _format_percent(passed, total),
        "top_fail_groups": fail_groups,
        "top_fail_reason": {
            "no_rule_matched": int(fail_reason_counter.get("no_rule_matched", 0)),
            "wrong_action": int(fail_reason_counter.get("wrong_action", 0)),
            "mask_missing": int(fail_reason_counter.get("mask_missing", 0)),
            "action_and_mask": int(fail_reason_counter.get("action_and_mask", 0)),
        },
    }


def main() -> int:
    args = _parse_args()
    input_path = Path(args.input).resolve()
    results_path = Path(args.results_out).resolve()
    summary_path = Path(args.summary_out).resolve()

    try:
        cases = _load_cases(input_path)
        scan_engine = _build_scan_engine()
        with Session(engine) as session:
            rule_set_id = _resolve_rule_set_id(session, args.rule_set_id)

        results = asyncio.run(
            _evaluate_cases(
                cases=cases,
                rule_set_id=rule_set_id,
                scan_engine=scan_engine,
            )
        )
        formatted_results = [_format_result_case(row) for row in results]
        summary = _build_summary(results=results)

        _write_json(results_path, formatted_results)
        _write_json(summary_path, summary)
    except FileNotFoundError as exc:
        print(f"[eval] missing file: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"[eval] invalid JSON input: {exc}", file=sys.stderr)
        return 1
    except OperationalError as exc:
        print(
            "[eval] database connection failed. Ensure the backend database is reachable "
            "from this shell (current DATABASE_URL may point to Docker host 'db').",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        return 2
    except ModuleNotFoundError as exc:
        print(
            "[eval] runtime dependency is missing while initializing the scan engine. "
            "Activate the project environment or start the backend environment used by this repo.",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        return 2
    except SystemExit as exc:
        print(
            "[eval] scan engine initialization exited early. In this repo that usually means "
            "Presidio/spaCy tried to auto-download a model but the current environment cannot run pip.",
            file=sys.stderr,
        )
        print(f"[eval] upstream exit code: {exc.code}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[eval] failed: {exc}", file=sys.stderr)
        return 1

    _print_console_summary(summary=summary, results=formatted_results)
    print()
    print(f"Results JSON: {results_path}")
    print(f"Summary JSON: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
