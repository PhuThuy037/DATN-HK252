from __future__ import annotations

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
from app.rule.schemas import CompanyRuleCreateIn, RuleContextTermIn
from app.rule.service import create_company_custom_rule
from app.rule_embedding.service import evaluate_semantic_assist_candidates


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _create_admin_and_company(*, session: Session, marker: str) -> tuple[User, Company]:
    actor = User(
        email=f"semantic.topic.evidence.{marker}@test.local",
        hashed_password="x",
        name=f"Semantic Topic Evidence {marker}",
        status=UserStatus.active,
        role=SystemRole.admin,
    )
    company = Company(
        name=f"Semantic Topic Evidence {marker}",
        status=CompanyStatus.active,
    )
    session.add(actor)
    session.add(company)
    session.commit()
    session.refresh(actor)
    session.refresh(company)
    return actor, company


def main() -> None:
    marker = str(int(time.time() * 1000))

    with Session(engine) as session:
        actor, company = _create_admin_and_company(session=session, marker=marker)
        created = create_company_custom_rule(
            session=session,
            company_id=company.id,
            actor_user_id=actor.id,
            payload=CompanyRuleCreateIn(
                stable_key=f"semantic.assist.topic.evidence.{marker}",
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

        runtime_rule_ids = [created.id]
        matched_context_keywords = ["bách khoa"]
        stable_key = str(created.stable_key)

        target_only_1 = evaluate_semantic_assist_candidates(
            session=session,
            query="Bách Khoa có mấy cơ sở?",
            runtime_rule_ids=runtime_rule_ids,
            matched_context_keywords=matched_context_keywords,
        )
        _assert(target_only_1.get("called") is True, f"must call semantic assist: {target_only_1}")
        _assert(
            stable_key in list(target_only_1.get("candidate_rule_keys") or []),
            f"candidate keys must include rule: {target_only_1}",
        )
        _assert(
            list(target_only_1.get("supported_rule_keys") or []) == [],
            f"target-only question must not support: {target_only_1}",
        )

        target_only_2 = evaluate_semantic_assist_candidates(
            session=session,
            query="Bách Khoa năm nay tuyển sinh ra sao?",
            runtime_rule_ids=runtime_rule_ids,
            matched_context_keywords=matched_context_keywords,
        )
        _assert(
            list(target_only_2.get("supported_rule_keys") or []) == [],
            f"neutral target-only question must not support: {target_only_2}",
        )

        topic_support_1 = evaluate_semantic_assist_candidates(
            session=session,
            query="Bách Khoa tăng mức thu trong năm nay phải không?",
            runtime_rule_ids=runtime_rule_ids,
            matched_context_keywords=matched_context_keywords,
        )
        _assert(
            stable_key in list(topic_support_1.get("supported_rule_keys") or []),
            f"topic paraphrase must support rule: {topic_support_1}",
        )

        topic_support_2 = evaluate_semantic_assist_candidates(
            session=session,
            query="Bách Khoa có định điều chỉnh học phí không?",
            runtime_rule_ids=runtime_rule_ids,
            matched_context_keywords=matched_context_keywords,
        )
        _assert(
            stable_key in list(topic_support_2.get("supported_rule_keys") or []),
            f"topic paraphrase must support rule: {topic_support_2}",
        )

    print("ALL PASS: semantic assist now requires topic evidence beyond target anchor.")


if __name__ == "__main__":
    main()
