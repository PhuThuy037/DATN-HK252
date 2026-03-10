from dataclasses import asdict
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.auth.deps import CurrentPrincipal
from app.common.enums import MemberRole
from app.decision.context_scorer import ContextScorer
from app.decision.context_term_runtime import load_context_runtime_overrides
from app.decision.decision_resolver import DecisionResolver
from app.decision.detectors.local_regex_detector import LocalRegexDetector
from app.permissions.core import forbid
from app.permissions.loaders.conversation import load_company_member_active_or_403
from app.rule.engine import RuleEngine


router = APIRouter(prefix="/v1/debug", tags=["Debug"])

detector = LocalRegexDetector()
context_scorer = ContextScorer("app/config/context_base.yaml")
rule_engine = RuleEngine()
resolver = DecisionResolver()


class FullScanRequest(BaseModel):
    text: str
    rule_set_id: UUID


class EntityOut(BaseModel):
    type: str
    start: int
    end: int
    score: float
    source: str
    text: str
    metadata: dict[str, Any]


class RuleMatchOut(BaseModel):
    rule_id: UUID
    stable_key: str
    name: str
    action: str
    priority: int


class FullScanResponse(BaseModel):
    ok: bool = True
    entities: list[EntityOut]
    signals: dict[str, Any]
    matched_rules: list[RuleMatchOut]
    final_action: str


@router.post("/full-scan", response_model=FullScanResponse)
def debug_full_scan(
    req: FullScanRequest,
    session: SessionDep,
    principal: CurrentPrincipal,
):
    member = load_company_member_active_or_403(
        session=session,
        company_id=req.rule_set_id,
        user_id=principal.user_id,
    )
    if member.role != MemberRole.company_admin:
        raise forbid(
            "Rule set owner required for debug full-scan",
            field="rule_set_id",
            reason="not_rule_set_owner",
        )

    overrides = load_context_runtime_overrides(
        session=session,
        company_id=req.rule_set_id,
    )

    # 1) Detect entities
    entities = detector.scan(
        req.text,
        context_hints_by_entity=overrides.regex_hints,
    )

    # 2) Context signals
    ctx = context_scorer.score(
        req.text,
        persona_keywords_override=overrides.persona_keywords,
    )
    signals = context_scorer.to_signals_dict(ctx)

    # 3) Rule matching
    matches = rule_engine.evaluate(
        session=session,
        company_id=req.rule_set_id,
        entities=entities,
        signals=signals,
    )

    # 4) Resolve decision
    decision = resolver.resolve(matches)

    return {
        "ok": True,
        "entities": [asdict(e) for e in entities],
        "signals": signals,
        "matched_rules": [
            {
                "rule_id": m.rule_id,
                "stable_key": m.stable_key,
                "name": m.name,
                "action": m.action.value,
                "priority": m.priority,
            }
            for m in decision.matched
        ],
        "final_action": decision.final_action.value,
    }
