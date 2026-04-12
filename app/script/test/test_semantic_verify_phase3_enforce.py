from __future__ import annotations

import asyncio
import time

import app.db.all_models  # noqa: F401
from sqlmodel import Session

from app.auth.model import User
from app.common.enums import (
    CompanyStatus,
    MatchMode,
    RagMode,
    RuleAction,
    RuleScope,
    RuleSeverity,
    SystemRole,
    UserStatus,
)
from app.company.model import Company
from app.db.engine import engine
from app.llm import LlmTextResult
from app.rule.schemas import CompanyRuleCreateIn, RuleContextTermIn
from app.rule.service import create_company_custom_rule


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _create_admin_and_company(*, session: Session, marker: str) -> tuple[User, Company]:
    actor = User(
        email=f"semantic.verify.phase3.{marker}@test.local",
        hashed_password="x",
        name=f"Semantic Verify Enforce {marker}",
        status=UserStatus.active,
        role=SystemRole.admin,
    )
    company = Company(
        name=f"Semantic Verify Enforce {marker}",
        status=CompanyStatus.active,
    )
    session.add(actor)
    session.add(company)
    session.commit()
    session.refresh(actor)
    session.refresh(company)
    return actor, company


async def main_async() -> None:
    import app.decision.scan_engine_local as scan_module

    class _StubPresidioDetector:
        def scan(self, text: str) -> list[object]:
            return []

    scan_module.PresidioDetector = _StubPresidioDetector
    scan = scan_module.ScanEngineLocal(context_yaml_path="app/config/context_base.yaml")

    async def _fake_call_llm(prompt: str) -> LlmTextResult:
        normalized = prompt.lower()
        if "dong cao hon" in normalized or "tang muc thu" in normalized:
            raw = '{"decision":"PASS","confidence":0.83,"reason":"topic_evidence_present"}'
        elif "muc phi tang" in normalized:
            raw = '{"decision":"PASS","confidence":0.44,"reason":"topic_evidence_weak"}'
        elif "dieu chinh hoc phi" in normalized:
            raw = '{"decision":"FAIL","confidence":0.82,"reason":"topic_not_specific_enough"}'
        else:
            raw = '{"decision":"UNSURE","confidence":0.35,"reason":"insufficient_context"}'
        return LlmTextResult(
            text=raw,
            provider="stub",
            model="stub-semantic-verify",
            fallback_used=False,
        )

    scan.rag._call_llm = _fake_call_llm  # type: ignore[method-assign]

    marker = str(int(time.time() * 1000))

    with Session(engine) as session:
        actor, company = _create_admin_and_company(session=session, marker=marker)
        semantic_rule = create_company_custom_rule(
            session=session,
            company_id=company.id,
            actor_user_id=actor.id,
            payload=CompanyRuleCreateIn(
                stable_key=f"semantic.verify.phase3.rule.{marker}",
                name="Bach Khoa Tang Hoc Phi Semantic",
                description="Sensitive topic about Bach Khoa increasing tuition fees",
                scope=RuleScope.chat,
                conditions={
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["bach khoa"],
                            }
                        },
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["tang hoc phi"],
                            }
                        },
                    ]
                },
                action=RuleAction.block,
                severity=RuleSeverity.high,
                priority=180,
                match_mode=MatchMode.keyword_plus_semantic,
                rag_mode=RagMode.off,
                enabled=True,
            ),
            context_terms=[
                RuleContextTermIn(
                    entity_type="SEM_TOPIC",
                    term="tang muc thu",
                    lang="vi",
                    weight=1.0,
                    window_1=60,
                    window_2=20,
                    enabled=True,
                ),
                RuleContextTermIn(
                    entity_type="SEM_TOPIC",
                    term="dieu chinh hoc phi",
                    lang="vi",
                    weight=1.0,
                    window_1=60,
                    window_2=20,
                    enabled=True,
                ),
                RuleContextTermIn(
                    entity_type="SEM_TOPIC",
                    term="dong cao hon",
                    lang="vi",
                    weight=1.0,
                    window_1=60,
                    window_2=20,
                    enabled=True,
                ),
            ],
        )

        exact_hit = await scan.scan(
            session=session,
            text="Truong Bach Khoa co tang hoc phi khong?",
            company_id=company.id,
            user_id=actor.id,
            scope=RuleScope.chat,
        )
        exact_signals = dict(exact_hit.get("signals") or {})
        _assert(
            str(exact_hit.get("final_action") or "").lower().endswith("block"),
            f"exact keyword hit must remain phase-1 block: {exact_hit}",
        )
        _assert(
            dict(exact_signals.get("semantic_verify") or {}).get("called") is False,
            f"exact keyword hit must not call verify: {exact_signals}",
        )
        _assert(
            exact_signals.get("semantic_verify_enforced") is False,
            f"exact keyword hit must not use semantic enforcement: {exact_signals}",
        )

        pass_case = await scan.scan(
            session=session,
            text="Em nghe noi Bach Khoa sap tang muc thu va sinh vien co the phai dong cao hon dung khong?",
            company_id=company.id,
            user_id=actor.id,
            scope=RuleScope.chat,
        )
        pass_signals = dict(pass_case.get("signals") or {})
        pass_verify = dict(pass_signals.get("semantic_verify") or {})
        pass_matches = list(pass_case.get("matches") or [])
        _assert(
            str(pass_case.get("final_action") or "").lower().endswith("block"),
            f"PASS verify >= 0.45 must enforce block: {pass_case}",
        )
        _assert(
            str(pass_verify.get("decision") or "") == "PASS",
            f"PASS case must preserve verify decision: {pass_verify}",
        )
        _assert(
            float(pass_verify.get("confidence") or 0.0) >= 0.45,
            f"PASS case must cross enforce threshold: {pass_verify}",
        )
        _assert(
            pass_signals.get("semantic_verify_enforced") is True,
            f"PASS case must set semantic_verify_enforced: {pass_signals}",
        )
        _assert(
            str(pass_signals.get("semantic_verify_enforced_rule_key") or "") == str(semantic_rule.stable_key),
            f"PASS case must expose enforced rule key: {pass_signals}",
        )
        _assert(
            str(pass_signals.get("semantic_verify_enforced_reason") or "") == "verify_pass_confident",
            f"PASS case must expose enforcement reason: {pass_signals}",
        )
        _assert(
            any(str(getattr(m, "stable_key", "") or "") == str(semantic_rule.stable_key) for m in pass_matches),
            f"PASS case must retain enforced rule in matches: {pass_matches}",
        )

        weak_pass_case = await scan.scan(
            session=session,
            text="Bach Khoa co muc phi tang trong thoi gian toi khong?",
            company_id=company.id,
            user_id=actor.id,
            scope=RuleScope.chat,
        )
        weak_pass_signals = dict(weak_pass_case.get("signals") or {})
        weak_pass_verify = dict(weak_pass_signals.get("semantic_verify") or {})
        _assert(
            str(weak_pass_case.get("final_action") or "").lower().endswith("allow"),
            f"PASS below threshold must stay allow: {weak_pass_case}",
        )
        _assert(
            str(weak_pass_verify.get("decision") or "") == "PASS",
            f"weak PASS case must preserve verify decision: {weak_pass_verify}",
        )
        _assert(
            float(weak_pass_verify.get("confidence") or 0.0) < 0.45,
            f"weak PASS case must remain below enforce threshold: {weak_pass_verify}",
        )
        _assert(
            weak_pass_signals.get("semantic_verify_enforced") is False,
            f"weak PASS case must not enforce: {weak_pass_signals}",
        )
        _assert(
            str(weak_pass_signals.get("semantic_verify_enforced_reason") or "")
            == "verify_confidence_below_threshold",
            f"weak PASS case must expose below-threshold reason: {weak_pass_signals}",
        )

        fail_case = await scan.scan(
            session=session,
            text="Bach Khoa co dinh dieu chinh hoc phi khong?",
            company_id=company.id,
            user_id=actor.id,
            scope=RuleScope.chat,
        )
        fail_signals = dict(fail_case.get("signals") or {})
        fail_verify = dict(fail_signals.get("semantic_verify") or {})
        _assert(
            str(fail_case.get("final_action") or "").lower().endswith("allow"),
            f"FAIL verify must stay allow: {fail_case}",
        )
        _assert(
            str(fail_verify.get("decision") or "") == "FAIL",
            f"FAIL case must keep verify decision: {fail_verify}",
        )
        _assert(
            fail_signals.get("semantic_verify_enforced") is False,
            f"FAIL case must not enforce: {fail_signals}",
        )
        _assert(
            str(fail_signals.get("semantic_verify_enforced_reason") or "") == "verify_fail",
            f"FAIL case must expose fail reason: {fail_signals}",
        )

        unsure_case = await scan.scan(
            session=session,
            text="Bach Khoa co tang loai phi nao gan day khong?",
            company_id=company.id,
            user_id=actor.id,
            scope=RuleScope.chat,
        )
        unsure_signals = dict(unsure_case.get("signals") or {})
        unsure_verify = dict(unsure_signals.get("semantic_verify") or {})
        _assert(
            str(unsure_case.get("final_action") or "").lower().endswith("allow"),
            f"UNSURE verify must stay allow: {unsure_case}",
        )
        _assert(
            str(unsure_verify.get("decision") or "") == "UNSURE",
            f"UNSURE case must keep verify decision: {unsure_verify}",
        )
        _assert(
            unsure_signals.get("semantic_verify_enforced") is False,
            f"UNSURE case must not enforce: {unsure_signals}",
        )
        _assert(
            str(unsure_signals.get("semantic_verify_enforced_reason") or "") == "verify_unsure",
            f"UNSURE case must expose unsure reason: {unsure_signals}",
        )

        neutral_case = await scan.scan(
            session=session,
            text="Bach Khoa co may co so?",
            company_id=company.id,
            user_id=actor.id,
            scope=RuleScope.chat,
        )
        neutral_signals = dict(neutral_case.get("signals") or {})
        _assert(
            str(neutral_case.get("final_action") or "").lower().endswith("allow"),
            f"neutral false-positive case must stay allow: {neutral_case}",
        )
        _assert(
            neutral_signals.get("semantic_verify_enforced") is False,
            f"neutral false-positive case must not enforce: {neutral_signals}",
        )

    print(
        "ALL PASS: semantic verify enforces only for PASS >= 0.45 and stays allow otherwise."
    )


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
