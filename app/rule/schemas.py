from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field as PydanticField

from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity


class RuleOrigin(str, Enum):
    global_default = "global_default"
    personal_override = "personal_override"
    personal_custom = "personal_custom"


class CompanyRuleOut(BaseModel):
    id: UUID
    rule_set_id: Optional[UUID] = None
    stable_key: str
    name: str
    description: Optional[str] = None
    scope: RuleScope
    conditions: dict[str, Any]
    conditions_version: int
    action: RuleAction
    severity: RuleSeverity
    priority: int
    rag_mode: RagMode
    enabled: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    origin: RuleOrigin
    can_edit_action: bool
    can_soft_delete: bool


class CompanyRuleCreateIn(BaseModel):
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


class RuleContextTermIn(BaseModel):
    entity_type: str = PydanticField(min_length=1, max_length=100)
    term: str = PydanticField(min_length=1, max_length=500)
    lang: str = PydanticField(default="vi", min_length=1, max_length=20)
    weight: float = 1.0
    window_1: int = 60
    window_2: int = 20
    enabled: bool = True


class CompanyRuleCreateWithContextIn(BaseModel):
    rule: CompanyRuleCreateIn
    context_terms: list[RuleContextTermIn] = PydanticField(default_factory=list)


class CompanyRuleUpdateIn(BaseModel):
    name: Optional[str] = PydanticField(default=None, min_length=1, max_length=300)
    description: Optional[str] = PydanticField(default=None, max_length=2000)
    scope: Optional[RuleScope] = None
    conditions: Optional[dict[str, Any]] = None
    action: Optional[RuleAction] = None
    severity: Optional[RuleSeverity] = None
    priority: Optional[int] = None
    rag_mode: Optional[RagMode] = None
    enabled: Optional[bool] = None


class CompanyRuleToggleEnabledIn(BaseModel):
    enabled: bool


class PersonalRuleOut(BaseModel):
    id: UUID
    stable_key: str
    name: str
    description: Optional[str] = None
    scope: RuleScope
    conditions: dict[str, Any]
    conditions_version: int
    action: RuleAction
    severity: RuleSeverity
    priority: int
    rag_mode: RagMode
    enabled: bool
    default_enabled: bool
    has_override: bool
    can_toggle_enabled: bool
    created_at: datetime
    updated_at: datetime


class PersonalRuleToggleEnabledIn(BaseModel):
    enabled: bool


class RuleChangeLogOut(BaseModel):
    id: UUID
    rule_set_id: UUID
    rule_id: UUID
    actor_user_id: UUID
    action: str
    changed_fields: list[str]
    before_json: Optional[dict[str, Any]] = None
    after_json: Optional[dict[str, Any]] = None
    created_at: datetime


class CompanyRuleCreateOut(CompanyRuleOut):
    context_term_ids: list[UUID] = PydanticField(default_factory=list)


class EffectiveRuleMeOut(BaseModel):
    rule_id: UUID
    stable_key: str
    name: str
    origin: RuleOrigin
    enabled: bool
    priority: int
    action: RuleAction


# Backward-compatible aliases for naming migration.
RuleSetRuleOut = CompanyRuleOut
RuleSetRuleCreateIn = CompanyRuleCreateIn
RuleSetRuleCreateWithContextIn = CompanyRuleCreateWithContextIn
RuleSetRuleCreateOut = CompanyRuleCreateOut
RuleSetRuleUpdateIn = CompanyRuleUpdateIn
RuleSetRuleToggleEnabledIn = CompanyRuleToggleEnabledIn
RuleSetRuleChangeLogOut = RuleChangeLogOut
