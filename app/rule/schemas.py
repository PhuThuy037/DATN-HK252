from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field as PydanticField

from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity


class RuleOrigin(str, Enum):
    global_default = "global_default"
    company_override = "company_override"
    company_custom = "company_custom"


class CompanyRuleOut(BaseModel):
    id: UUID
    company_id: Optional[UUID] = None
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
