from dataclasses import asdict
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.decision.detectors.local_regex_detector import LocalRegexDetector
from app.decision.context_scorer import ContextScorer
from app.rule.engine import RuleEngine
from app.decision.decision_resolver import DecisionResolver


router = APIRouter(prefix="/v1/debug", tags=["Debug"])

detector = LocalRegexDetector()
context_scorer = ContextScorer("app/config/context_base.yaml")
rule_engine = RuleEngine()
resolver = DecisionResolver()


# =============================
# REQUEST / RESPONSE MODELS
# =============================


class FullScanRequest(BaseModel):
    text: str
    company_id: Optional[UUID] = None


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


# =============================
# FULL SCAN ENDPOINT
# =============================


@router.post("/full-scan", response_model=FullScanResponse)
def debug_full_scan(req: FullScanRequest, session: SessionDep):

    # 1️⃣ Detect entities
    entities = detector.scan(req.text)

    # 2️⃣ Context signals
    ctx = context_scorer.score(req.text)
    signals = context_scorer.to_signals_dict(ctx)

    # 3️⃣ Rule matching
    matches = rule_engine.evaluate(
        session=session,
        company_id=req.company_id,
        entities=entities,
        signals=signals,
    )

    # 4️⃣ Decision resolve
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