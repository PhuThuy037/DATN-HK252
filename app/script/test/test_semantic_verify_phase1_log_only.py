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
        email=f"semantic.verify.phase1.{marker}@test.local",
        hashed_password="x",
        name=f"Semantic Verify {marker}",
        status=UserStatus.active,
        role=SystemRole.admin,
    )
    company = Company(
        name=f"Semantic Verify {marker}",
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

    verify_prompts: list[str] = []

    async def _fake_call_llm(prompt: str) -> LlmTextResult:
        verify_prompts.append(prompt)
        return LlmTextResult(
            text='{"decision":"UNSURE","confidence":0.41,"reason":"needs_human_review"}',
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
                stable_key=f"semantic.verify.phase1.rule.{marker}",
                name="Bach Khoa Tang Hoc Phi Semantic",
                description="Sensitive topic about Bach Khoa increasing tuition fees",
                scope=RuleScope.chat,
                conditions={
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["bách khoa"],
                            }
                        },
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["tăng học phí"],
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
                    term="tăng mức thu",
                    lang="vi",
                    weight=1.0,
                    window_1=60,
                    window_2=20,
                    enabled=True,
                ),
                RuleContextTermIn(
                    entity_type="SEM_TOPIC",
                    term="điều chỉnh học phí",
                    lang="vi",
                    weight=1.0,
                    window_1=60,
                    window_2=20,
                    enabled=True,
                ),
                RuleContextTermIn(
                    entity_type="SEM_TOPIC",
                    term="đóng cao hơn",
                    lang="vi",
                    weight=1.0,
                    window_1=60,
                    window_2=20,
                    enabled=True,
                ),
            ],
        )

        create_company_custom_rule(
            session=session,
            company_id=company.id,
            actor_user_id=actor.id,
            payload=CompanyRuleCreateIn(
                stable_key=f"semantic.verify.phase1.mask.{marker}",
                name="Mask phone numbers",
                description="Force phase-1 mask short-circuit",
                scope=RuleScope.chat,
                conditions={"entity_type": "PHONE"},
                action=RuleAction.mask,
                severity=RuleSeverity.medium,
                priority=300,
                match_mode=MatchMode.strict_keyword,
                rag_mode=RagMode.off,
                enabled=True,
            ),
        )

        exact_hit = await scan.scan(
            session=session,
            text="Trường Bách Khoa có tăng học phí không?",
            company_id=company.id,
            user_id=actor.id,
            scope=RuleScope.chat,
        )
        exact_signals = dict(exact_hit.get("signals") or {})
        exact_semantic = dict(exact_signals.get("semantic_assist") or {})
        exact_verify = dict(exact_signals.get("semantic_verify") or {})
        _assert(
            str(exact_hit.get("final_action") or "").lower().endswith("block"),
            f"exact keyword hit must block by phase-1: {exact_hit}",
        )
        _assert(
            exact_semantic.get("called") is False,
            f"semantic assist must not run after exact phase-1 block: {exact_semantic}",
        )
        _assert(
            exact_verify.get("called") is False,
            f"semantic verify must not run after exact phase-1 block: {exact_verify}",
        )
        _assert(
            exact_signals.get("semantic_verify_enforced") is False,
            f"exact keyword hit must not enforce via verify: {exact_signals}",
        )
        _assert(len(verify_prompts) == 0, f"verify llm must not be called: {verify_prompts}")

        near_meaning = await scan.scan(
            session=session,
            text="Em nghe nói Bách Khoa sắp tăng mức thu và sinh viên có thể phải đóng cao hơn đúng không?",
            company_id=company.id,
            user_id=actor.id,
            scope=RuleScope.chat,
        )
        near_signals = dict(near_meaning.get("signals") or {})
        near_semantic = dict(near_signals.get("semantic_assist") or {})
        near_verify = dict(near_signals.get("semantic_verify") or {})
        _assert(
            str(near_meaning.get("final_action") or "").lower().endswith("allow"),
            f"near-meaning semantic verify must stay log-only: {near_meaning}",
        )
        _assert(
            str(semantic_rule.stable_key) in list(near_semantic.get("supported_rule_keys") or []),
            f"near-meaning case must have semantic support: {near_semantic}",
        )
        _assert(
            float(near_semantic.get("top_confidence") or 0.0) >= 0.40,
            f"near-meaning case must cross verify threshold: {near_semantic}",
        )
        _assert(
            near_verify.get("called") is True,
            f"semantic verify must be called for strong support: {near_verify}",
        )
        _assert(
            str(near_verify.get("rule_key") or "") == str(semantic_rule.stable_key),
            f"semantic verify must target top supported rule: {near_verify}",
        )
        _assert(
            str(near_verify.get("decision") or "") in {"PASS", "FAIL", "UNSURE"},
            f"semantic verify decision must be set: {near_verify}",
        )
        _assert(
            near_signals.get("semantic_verify_enforced") is False,
            f"phase-1 log-only path must not enforce on UNSURE: {near_signals}",
        )
        _assert(
            str(near_signals.get("semantic_verify_enforced_reason") or "")
            == "verify_unsure",
            f"phase-1 log-only path must keep explicit enforce reason: {near_signals}",
        )
        _assert(len(verify_prompts) == 1, f"verify llm must be called once: {verify_prompts}")

        for text in [
            "Bách Khoa có mấy cơ sở?",
            "Bách Khoa tuyển sinh ra sao?",
            "Bách Khoa có học bổng không?",
        ]:
            out = await scan.scan(
                session=session,
                text=text,
                company_id=company.id,
                user_id=actor.id,
                scope=RuleScope.chat,
            )
            signals = dict(out.get("signals") or {})
            semantic = dict(signals.get("semantic_assist") or {})
            verify = dict(signals.get("semantic_verify") or {})
            _assert(
                str(out.get("final_action") or "").lower().endswith("allow"),
                f"false-positive case must remain allow: text={text} out={out}",
            )
            _assert(
                list(semantic.get("supported_rule_keys") or []) == [],
                f"false-positive case must not have supported semantic rule: text={text} semantic={semantic}",
            )
            _assert(
                verify.get("called") is False,
                f"semantic verify must not run below threshold or without support: text={text} verify={verify}",
            )
            _assert(
                signals.get("semantic_verify_enforced") is False,
                f"false-positive case must not enforce: text={text} signals={signals}",
            )

        _assert(len(verify_prompts) == 1, f"verify llm must still have only one call: {verify_prompts}")

        mask_case = await scan.scan(
            session=session,
            text="Số điện thoại liên hệ 0901234567 để trao đổi tiếp",
            company_id=company.id,
            user_id=actor.id,
            scope=RuleScope.chat,
        )
        mask_signals = dict(mask_case.get("signals") or {})
        mask_verify = dict(mask_signals.get("semantic_verify") or {})
        _assert(
            str(mask_case.get("final_action") or "").lower().endswith("mask"),
            f"phase-1 mask must short-circuit: {mask_case}",
        )
        _assert(
            mask_verify.get("called") is False,
            f"semantic verify must not run after phase-1 mask: {mask_verify}",
        )
        _assert(
            mask_signals.get("semantic_verify_enforced") is False,
            f"phase-1 mask must never set verify enforcement: {mask_signals}",
        )
        _assert(len(verify_prompts) == 1, f"verify llm must not be called on mask path: {verify_prompts}")

    print("ALL PASS: semantic verify phase-1 log-only behavior is correct.")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
