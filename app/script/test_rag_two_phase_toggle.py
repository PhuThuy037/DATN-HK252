from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from uuid import UUID

import app.db.all_models  # noqa: F401
from sqlmodel import Session, select

from app.auth.model import User
from app.common.enums import (
    CompanyStatus,
    RagMode,
    RuleAction,
    RuleScope,
    RuleSeverity,
    UserStatus,
)
from app.company.model import Company
from app.db.engine import engine
from app.decision.scan_engine_local import ScanEngineLocal
from app.rule.model import Rule
from app.rule.seed import RuleSeeder
from app.rule.engine import RuleEngine

RAG_BLOCK_KEY = "global.security.rag.block"
RAG_MASK_KEY = "global.security.rag.mask"
PHONE_MASK_KEY = "global.pii.phone.mask"


class ForcedRagGateScanEngine(ScanEngineLocal):
    def _should_call_rag(
        self,
        *,
        sec_decision: str,
        sec_score: float,
        persona: str | None,
        context_keywords: list[str],
        entities: list[object],
        spoken_entities: list[object],
    ) -> bool:
        return True


class FakeRag:
    def __init__(self, decision: str):
        self.decision = str(decision).upper()
        self.calls = 0

    async def decide(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            decision=self.decision,
            confidence=0.93,
            rule_keys=[],
            rationale="fake-rag",
        )


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _action_name(value: object) -> str:
    if hasattr(value, "value"):
        return str(getattr(value, "value") or "").strip().lower()
    return str(value or "").strip().lower()


def _ensure_active_user(session: Session) -> User:
    row = session.exec(
        select(User)
        .where(User.status == UserStatus.active)
        .order_by(User.created_at.asc())
    ).first()
    if row is not None:
        return row

    row = User(
        email=f"seed-rag-{int(time.time())}@local.test",
        hashed_password="not-used",
        name="Seed Rag",
        status=UserStatus.active,
    )
    session.add(row)
    session.flush()
    return row


def _ensure_seed_rules(session: Session, created_by_user_id: UUID) -> None:
    seeder = RuleSeeder("app/config/seed_rules.yaml")
    seeder.upsert_global_rules(session=session, created_by_user_id=created_by_user_id)


def _get_global_rule(session: Session, stable_key: str) -> Rule:
    row = session.exec(
        select(Rule)
        .where(Rule.rule_set_id.is_(None))
        .where(Rule.stable_key == stable_key)
        .order_by(Rule.created_at.desc())
    ).first()
    if row is None:
        raise AssertionError(f"missing global rule: {stable_key}")
    return row


def _upsert_company_override(
    session: Session,
    *,
    rule_set_id: UUID,
    global_rule: Rule,
    enabled: bool,
    created_by: UUID,
) -> Rule:
    row = session.exec(
        select(Rule)
        .where(Rule.rule_set_id == rule_set_id)
        .where(Rule.stable_key == global_rule.stable_key)
        .order_by(Rule.created_at.desc())
    ).first()

    if row is None:
        row = Rule(
            rule_set_id=rule_set_id,
            stable_key=global_rule.stable_key,
            name=global_rule.name,
            description=global_rule.description,
            scope=global_rule.scope,
            conditions=global_rule.conditions,
            conditions_version=global_rule.conditions_version,
            action=global_rule.action,
            severity=global_rule.severity,
            priority=global_rule.priority,
            rag_mode=global_rule.rag_mode,
            enabled=bool(enabled),
            created_by=created_by,
        )
    else:
        row.enabled = bool(enabled)

    session.add(row)
    session.flush()
    return row


def _create_or_update_force_mask_rule(
    session: Session,
    *,
    rule_set_id: UUID,
    created_by: UUID,
    stable_key: str,
    enabled: bool,
) -> Rule:
    row = session.exec(
        select(Rule)
        .where(Rule.rule_set_id == rule_set_id)
        .where(Rule.stable_key == stable_key)
        .order_by(Rule.created_at.desc())
    ).first()

    conditions = {"any": [{"signal": {"field": "security.prompt_injection", "equals": False}}]}

    if row is None:
        row = Rule(
            rule_set_id=rule_set_id,
            stable_key=stable_key,
            name="Force local mask for two-phase test",
            description="deterministic local mask",
            scope=RuleScope.prompt,
            conditions=conditions,
            conditions_version=1,
            action=RuleAction.mask,
            severity=RuleSeverity.medium,
            priority=240,
            rag_mode=RagMode.off,
            enabled=bool(enabled),
            created_by=created_by,
        )
    else:
        row.enabled = bool(enabled)
        row.conditions = conditions
        row.action = RuleAction.mask
        row.priority = 240

    session.add(row)
    session.flush()
    return row


async def _run_scan_case(
    *,
    rule_set_id: UUID,
    user_id: UUID,
    force_key: str,
    rag_decision: str,
    force_enabled: bool,
    rag_block_enabled: bool,
    rag_mask_enabled: bool,
    text: str = "hello team, this is a normal message",
    phone_mask_enabled: bool | None = None,
) -> tuple[dict, int]:
    with Session(engine) as session:
        g_block = _get_global_rule(session, RAG_BLOCK_KEY)
        g_mask = _get_global_rule(session, RAG_MASK_KEY)
        _upsert_company_override(
            session,
            rule_set_id=rule_set_id,
            global_rule=g_block,
            enabled=rag_block_enabled,
            created_by=user_id,
        )
        _upsert_company_override(
            session,
            rule_set_id=rule_set_id,
            global_rule=g_mask,
            enabled=rag_mask_enabled,
            created_by=user_id,
        )
        if phone_mask_enabled is not None:
            g_phone = _get_global_rule(session, PHONE_MASK_KEY)
            _upsert_company_override(
                session,
                rule_set_id=rule_set_id,
                global_rule=g_phone,
                enabled=bool(phone_mask_enabled),
                created_by=user_id,
            )
        _create_or_update_force_mask_rule(
            session,
            rule_set_id=rule_set_id,
            created_by=user_id,
            stable_key=force_key,
            enabled=force_enabled,
        )
        session.commit()

    RuleEngine.invalidate_cache(rule_set_id)

    scan = ForcedRagGateScanEngine(context_yaml_path="app/config/context_base.yaml")
    fake_rag = FakeRag(decision=rag_decision)
    scan.rag = fake_rag  # type: ignore[assignment]

    with Session(engine) as session:
        out = await scan.scan(
            session=session,
            text=text,
            rule_set_id=rule_set_id,
            user_id=None,
        )

    return out, int(fake_rag.calls)


async def main_async() -> None:
    marker = int(time.time())

    with Session(engine) as session:
        user = _ensure_active_user(session)
        session.commit()
        user_id = user.id

    with Session(engine) as session:
        _ensure_seed_rules(session, created_by_user_id=user_id)

    with Session(engine) as session:
        company = Company(name=f"Two-phase RAG test {marker}", status=CompanyStatus.active)
        session.add(company)
        session.commit()
        session.refresh(company)
        rule_set_id = company.id

    force_key = f"company.test.two_phase.force_mask.{marker}"

    # Case 1: local phase-1 mask => do not call RAG.
    out1, calls1 = await _run_scan_case(
        rule_set_id=rule_set_id,
        user_id=user_id,
        force_key=force_key,
        rag_decision="BLOCK",
        force_enabled=True,
        rag_block_enabled=True,
        rag_mask_enabled=True,
    )
    _assert(_action_name(out1.get("final_action")) == "mask", "case1 final_action must be mask")
    _assert(calls1 == 0, f"case1 expected 0 rag calls, got {calls1}")
    _assert(bool(out1.get("ambiguous")) is False, "case1 ambiguous must be false")
    _assert("rag" not in (out1.get("signals") or {}), "case1 signals.rag must be absent")

    # Case 2: phase-1 allow + rag block/mask both OFF => skip RAG.
    out2, calls2 = await _run_scan_case(
        rule_set_id=rule_set_id,
        user_id=user_id,
        force_key=force_key,
        rag_decision="MASK",
        force_enabled=False,
        rag_block_enabled=False,
        rag_mask_enabled=False,
    )
    _assert(_action_name(out2.get("final_action")) == "allow", "case2 final_action must be allow")
    _assert(calls2 == 0, f"case2 expected 0 rag calls, got {calls2}")
    _assert(bool(out2.get("ambiguous")) is False, "case2 ambiguous must be false")

    # Case 3: phase-1 allow + only rag.mask ON + RAG returns BLOCK => downgrade to ALLOW.
    out3, calls3 = await _run_scan_case(
        rule_set_id=rule_set_id,
        user_id=user_id,
        force_key=force_key,
        rag_decision="BLOCK",
        force_enabled=False,
        rag_block_enabled=False,
        rag_mask_enabled=True,
    )
    _assert(calls3 == 1, f"case3 expected 1 rag call, got {calls3}")
    _assert(_action_name(out3.get("final_action")) == "allow", "case3 final_action must be allow")
    _assert(bool(out3.get("ambiguous")) is True, "case3 ambiguous must be true")
    sig3 = out3.get("signals") or {}
    rag3 = sig3.get("rag") or {}
    _assert(str(rag3.get("decision_raw", "")).upper() == "BLOCK", "case3 raw decision must be BLOCK")
    _assert(str(rag3.get("decision", "")).upper() == "ALLOW", "case3 effective decision must be ALLOW")

    # Case 4: phase-1 allow + only rag.mask ON + RAG returns MASK => final MASK.
    out4, calls4 = await _run_scan_case(
        rule_set_id=rule_set_id,
        user_id=user_id,
        force_key=force_key,
        rag_decision="MASK",
        force_enabled=False,
        rag_block_enabled=False,
        rag_mask_enabled=True,
    )
    _assert(calls4 == 1, f"case4 expected 1 rag call, got {calls4}")
    _assert(_action_name(out4.get("final_action")) == "mask", "case4 final_action must be mask")
    keys4 = [str(getattr(m, "stable_key", "")) for m in (out4.get("matches") or [])]
    _assert(RAG_MASK_KEY in keys4, f"case4 expected matched {RAG_MASK_KEY}, got {keys4}")

    # Case 5: simple PII only + phase-1 no-match => RAG must not override (Option 1 guard).
    out5, calls5 = await _run_scan_case(
        rule_set_id=rule_set_id,
        user_id=user_id,
        force_key=force_key,
        rag_decision="MASK",
        force_enabled=False,
        rag_block_enabled=True,
        rag_mask_enabled=True,
        text="So dien thoai test 0901234567",
        phone_mask_enabled=False,
    )
    _assert(calls5 == 0, f"case5 expected 0 rag calls, got {calls5}")
    _assert(_action_name(out5.get("final_action")) == "allow", "case5 final_action must be allow")
    _assert(bool(out5.get("ambiguous")) is False, "case5 ambiguous must be false")

    print("ALL PASS: two-phase RAG gating + effective toggle behavior is correct.")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()



