from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field as PydanticField, field_validator

from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity


class SuggestionStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    applied = "applied"
    rejected = "rejected"
    expired = "expired"
    failed = "failed"


class DuplicateDecision(str, Enum):
    exact_duplicate = "EXACT_DUPLICATE"
    near_duplicate = "NEAR_DUPLICATE"
    different = "DIFFERENT"


class RuleSuggestionDraftRule(BaseModel):
    stable_key: str = PydanticField(min_length=1, max_length=200)
    name: str = PydanticField(min_length=1, max_length=300)
    description: Optional[str] = PydanticField(default=None, max_length=2000)
    scope: RuleScope = RuleScope.prompt
    conditions: dict[str, Any]
    action: RuleAction = RuleAction.mask
    severity: RuleSeverity = RuleSeverity.medium
    priority: int = 0
    rag_mode: RagMode = RagMode.off
    enabled: bool = True


class RuleSuggestionDraftContextTerm(BaseModel):
    entity_type: str = PydanticField(min_length=1, max_length=100)
    term: str = PydanticField(min_length=1, max_length=500)
    lang: str = PydanticField(default="vi", min_length=1, max_length=20)
    weight: float = 1.0
    window_1: int = 60
    window_2: int = 20
    enabled: bool = True


class RuleSuggestionDraftPayload(BaseModel):
    rule: RuleSuggestionDraftRule
    context_terms: list[RuleSuggestionDraftContextTerm] = PydanticField(
        default_factory=list
    )


class RuleSuggestionGenerateIn(BaseModel):
    prompt: str = PydanticField(min_length=1, max_length=8000)


class RuleSuggestionEditIn(BaseModel):
    draft: RuleSuggestionDraftPayload
    expected_version: Optional[int] = PydanticField(default=None, ge=1)


class RuleSuggestionRejectIn(BaseModel):
    reason: Optional[str] = PydanticField(default=None, max_length=1000)
    expected_version: Optional[int] = PydanticField(default=None, ge=1)


class RuleSuggestionConfirmIn(BaseModel):
    reason: Optional[str] = PydanticField(default=None, max_length=1000)
    expected_version: Optional[int] = PydanticField(default=None, ge=1)


class RuleSuggestionApplyIn(BaseModel):
    expected_version: Optional[int] = PydanticField(default=None, ge=1)


class RuleSuggestionApplyOut(BaseModel):
    rule_id: UUID
    context_term_ids: list[UUID]


class RuleSuggestionSimulateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    samples: list[str] = PydanticField(min_length=1, max_length=100)
    include_examples: bool = True

    @field_validator("samples")
    @classmethod
    def _validate_samples(cls, value: list[str]) -> list[str]:
        out: list[str] = []
        for idx, raw in enumerate(value):
            text = str(raw or "").strip()
            if not text:
                raise ValueError(f"samples[{idx}] must be non-empty")
            if len(text) > 2000:
                raise ValueError(f"samples[{idx}] exceeds 2000 characters")
            out.append(text)
        return out


class RuleSuggestionSimulateResultOut(BaseModel):
    content: str
    matched: bool
    predicted_action: str


class RuleSuggestionSimulateOut(BaseModel):
    suggestion_id: UUID
    sample_size: int
    runtime_usable: bool = True
    runtime_warnings: list[str] = PydanticField(default_factory=list)
    matched_count: int
    action_breakdown: dict[str, int]
    results: list[RuleSuggestionSimulateResultOut] = PydanticField(
        default_factory=list
    )


class RuleDuplicateCandidateOut(BaseModel):
    rule_id: UUID
    stable_key: str
    name: str
    origin: str
    similarity: float
    lexical_score: float


class RuleDuplicateCheckOut(BaseModel):
    decision: DuplicateDecision
    confidence: float
    rationale: str
    matched_rule_ids: list[UUID] = PydanticField(default_factory=list)
    candidates: list[RuleDuplicateCandidateOut] = PydanticField(default_factory=list)
    top_k: int
    exact_threshold: float
    near_threshold: float
    source: str
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_fallback_used: bool = False


class RuleSuggestionExplanationOut(BaseModel):
    summary: str
    detected_intent: str
    derived_terms: list[str] = PydanticField(default_factory=list)
    action_reason: str


class RuleSuggestionQualitySignalsOut(BaseModel):
    intent_confidence: float = PydanticField(ge=0.0, le=1.0)
    duplicate_risk: str
    conflict_risk: str
    generation_source: str
    has_policy_context: bool
    intent_guard_applied: bool = False
    intent_mismatch_detected: bool = False
    runtime_usable: bool = True
    runtime_warnings: list[str] = PydanticField(default_factory=list)


class RuleSuggestionRetrievalContextOut(BaseModel):
    has_policy_context: bool = False
    policy_chunk_ids: list[str] = PydanticField(default_factory=list)
    related_rule_ids: list[str] = PydanticField(default_factory=list)


class RuleSuggestionOut(BaseModel):
    id: UUID
    rule_set_id: UUID
    created_by: UUID
    status: SuggestionStatus
    type: str
    version: int
    nl_input: str
    dedupe_key: str
    draft: RuleSuggestionDraftPayload
    applied_result_json: Optional[dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class RuleSuggestionGenerateOut(RuleSuggestionOut):
    duplicate_check: RuleDuplicateCheckOut
    explanation: RuleSuggestionExplanationOut
    quality_signals: RuleSuggestionQualitySignalsOut
    retrieval_context: RuleSuggestionRetrievalContextOut


class RuleSuggestionGetOut(RuleSuggestionOut):
    explanation: RuleSuggestionExplanationOut
    quality_signals: RuleSuggestionQualitySignalsOut


class RuleSuggestionLogOut(BaseModel):
    id: UUID
    suggestion_id: UUID
    rule_set_id: UUID
    actor_user_id: UUID
    action: str
    reason: Optional[str] = None
    before_json: Optional[dict[str, Any]] = None
    after_json: Optional[dict[str, Any]] = None
    created_at: datetime
