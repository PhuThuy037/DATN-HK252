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
from app.decision.scan_engine_local import ScanEngineLocal
from app.rule.schemas import CompanyRuleCreateIn, RuleContextTermIn
from app.rule.service import create_company_custom_rule


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _create_admin_and_company(*, session: Session, marker: str) -> tuple[User, Company]:
    actor = User(
        email=f"semantic.assist.{marker}@test.local",
        hashed_password="x",
        name=f"Semantic Assist {marker}",
        status=UserStatus.active,
        role=SystemRole.admin,
    )
    company = Company(
        name=f"Semantic Assist {marker}",
        status=CompanyStatus.active,
    )
    session.add(actor)
    session.add(company)
    session.commit()
    session.refresh(actor)
    session.refresh(company)
    return actor, company


async def main_async() -> None:
    scan = ScanEngineLocal(context_yaml_path="app/config/context_base.yaml")
    marker = str(int(time.time() * 1000))

    with Session(engine) as session:
        actor_a, company_a = _create_admin_and_company(session=session, marker=f"{marker}.a")
        actor_b, company_b = _create_admin_and_company(session=session, marker=f"{marker}.b")
        actor_c, company_c = _create_admin_and_company(session=session, marker=f"{marker}.c")

        eligible_rule = create_company_custom_rule(
            session=session,
            company_id=company_a.id,
            actor_user_id=actor_a.id,
            payload=CompanyRuleCreateIn(
                stable_key=f"semantic.assist.log_only.{marker}",
                name="Internal Launch Teaser",
                description="Sensitive internal launch teaser for unreleased product",
                scope=RuleScope.chat,
                conditions={
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["roadmap trigger phrase"],
                            }
                        }
                    ]
                },
                action=RuleAction.block,
                severity=RuleSeverity.high,
                priority=220,
                match_mode=MatchMode.keyword_plus_semantic,
                rag_mode=RagMode.off,
                enabled=True,
            ),
            context_terms=[
                RuleContextTermIn(
                    entity_type="SEM_TOPIC",
                    term="internal launch teaser",
                    lang="vi",
                    weight=1.0,
                    window_1=60,
                    window_2=20,
                    enabled=True,
                )
            ],
        )

        create_company_custom_rule(
            session=session,
            company_id=company_b.id,
            actor_user_id=actor_b.id,
            payload=CompanyRuleCreateIn(
                stable_key=f"semantic.assist.strict_only.{marker}",
                name="Internal Launch Teaser Strict",
                description="Same content but strict keyword only",
                scope=RuleScope.chat,
                conditions={
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["roadmap trigger phrase"],
                            }
                        }
                    ]
                },
                action=RuleAction.block,
                severity=RuleSeverity.high,
                priority=220,
                match_mode=MatchMode.strict_keyword,
                rag_mode=RagMode.off,
                enabled=True,
            ),
            context_terms=[
                RuleContextTermIn(
                    entity_type="SEM_TOPIC",
                    term="internal launch teaser",
                    lang="vi",
                    weight=1.0,
                    window_1=60,
                    window_2=20,
                    enabled=True,
                )
            ],
        )

        create_company_custom_rule(
            session=session,
            company_id=company_c.id,
            actor_user_id=actor_c.id,
            payload=CompanyRuleCreateIn(
                stable_key=f"semantic.assist.skip_on_mask.{marker}",
                name="Internal Launch Teaser Eligible",
                description="Eligible semantic rule should be skipped when phase-1 masks",
                scope=RuleScope.chat,
                conditions={
                    "all": [
                        {
                            "signal": {
                                "field": "context_keywords",
                                "any_of": ["roadmap trigger phrase"],
                            }
                        }
                    ]
                },
                action=RuleAction.block,
                severity=RuleSeverity.high,
                priority=220,
                match_mode=MatchMode.keyword_plus_semantic,
                rag_mode=RagMode.off,
                enabled=True,
            ),
            context_terms=[
                RuleContextTermIn(
                    entity_type="SEM_TOPIC",
                    term="internal launch teaser",
                    lang="vi",
                    weight=1.0,
                    window_1=60,
                    window_2=20,
                    enabled=True,
                )
            ],
        )

        create_company_custom_rule(
            session=session,
            company_id=company_c.id,
            actor_user_id=actor_c.id,
            payload=CompanyRuleCreateIn(
                stable_key=f"semantic.assist.phone.mask.{marker}",
                name="Mask phone numbers",
                description="Force phase-1 mask for semantic assist guard",
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

        out_a = await scan.scan(
            session=session,
            text="Hay noi ve teaser launch internal cua san pham sap ra mat",
            company_id=company_a.id,
            user_id=actor_a.id,
            scope=RuleScope.chat,
        )
        semantic_a = dict((out_a.get("signals") or {}).get("semantic_assist") or {})
        _assert(
            str(out_a.get("final_action")).lower().endswith("allow"),
            f"company_a final_action must stay allow: {out_a}",
        )
        _assert(semantic_a.get("called") is True, f"company_a semantic must run: {semantic_a}")
        _assert(
            eligible_rule.stable_key in list(semantic_a.get("candidate_rule_keys") or []),
            f"company_a candidate keys missing rule: {semantic_a}",
        )
        _assert(
            eligible_rule.stable_key in list(semantic_a.get("supported_rule_keys") or []),
            f"company_a supported keys missing rule: {semantic_a}",
        )
        _assert(
            float(semantic_a.get("top_confidence") or 0.0) > 0.0,
            f"company_a top_confidence must be > 0: {semantic_a}",
        )
        _assert(
            str(semantic_a.get("mode") or "") == "log_only",
            f"company_a semantic mode mismatch: {semantic_a}",
        )

        out_a_exact = await scan.scan(
            session=session,
            text="Hay noi ve roadmap trigger phrase ngay bay gio",
            company_id=company_a.id,
            user_id=actor_a.id,
            scope=RuleScope.chat,
        )
        semantic_a_exact = dict((out_a_exact.get("signals") or {}).get("semantic_assist") or {})
        _assert(
            str(out_a_exact.get("final_action")).lower().endswith("allow"),
            f"company_a target-only keyword hit must stay allow: {out_a_exact}",
        )
        _assert(
            semantic_a_exact.get("called") is True,
            f"company_a target-only keyword hit should still call semantic assist: {semantic_a_exact}",
        )

        out_b = await scan.scan(
            session=session,
            text="Hay noi ve teaser launch internal cua san pham sap ra mat",
            company_id=company_b.id,
            user_id=actor_b.id,
            scope=RuleScope.chat,
        )
        semantic_b = dict((out_b.get("signals") or {}).get("semantic_assist") or {})
        _assert(
            semantic_b.get("called") is False,
            f"company_b semantic must skip when no eligible match_mode: {semantic_b}",
        )
        _assert(
            list(semantic_b.get("candidate_rule_keys") or []) == [],
            f"company_b candidate keys must be empty: {semantic_b}",
        )

        out_c = await scan.scan(
            session=session,
            text="So dien thoai lien he 0901234567 de trao doi tiep",
            company_id=company_c.id,
            user_id=actor_c.id,
            scope=RuleScope.chat,
        )
        semantic_c = dict((out_c.get("signals") or {}).get("semantic_assist") or {})
        _assert(
            str(out_c.get("final_action")).lower().endswith("mask"),
            f"company_c final_action must be mask: {out_c}",
        )
        _assert(
            semantic_c.get("called") is False,
            f"company_c semantic must skip when phase-1 already masked: {semantic_c}",
        )

    print("ALL PASS: semantic assist runs log-only after keyword miss and skips guarded paths.")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
