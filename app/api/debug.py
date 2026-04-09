from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.auth.deps import require_admin
from app.company.model import Company
from app.decision.scan_engine_local import ScanEngineLocal
from app.decision.serializers import entity_to_dict, rulematch_to_dict
from app.permissions.core import not_found


router = APIRouter(
    prefix="/v1/debug",
    tags=["Debug"],
    dependencies=[Depends(require_admin)],
)

scan_engine = ScanEngineLocal(context_yaml_path="app/config/context_base.yaml")


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
async def debug_full_scan(
    req: FullScanRequest,
    session: SessionDep,
):
    company = session.get(Company, req.rule_set_id)
    if company is None:
        raise not_found("Rule set not found", field="rule_set_id")

    scan_out = await scan_engine.scan(
        session=session,
        text=req.text,
        company_id=req.rule_set_id,
        user_id=None,
    )

    return {
        "ok": True,
        "entities": [entity_to_dict(e) for e in scan_out["entities"]],
        "signals": dict(scan_out["signals"]),
        "matched_rules": [
            {
                "rule_id": row["rule_id"],
                "stable_key": row["stable_key"],
                "name": row["name"],
                "action": row["action"],
                "priority": row["priority"],
            }
            for row in [rulematch_to_dict(m) for m in scan_out["matches"]]
        ],
        "final_action": scan_out["final_action"].value,
    }
