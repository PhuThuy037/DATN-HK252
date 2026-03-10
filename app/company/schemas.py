from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field as PydanticField

from app.common.enums import CompanyStatus, MemberRole, MemberStatus


class RuleSetCreateIn(BaseModel):
    name: str = PydanticField(min_length=1, max_length=200)


class RuleSetOut(BaseModel):
    id: UUID
    name: str
    status: CompanyStatus
    created_at: datetime
    my_role: MemberRole


class CompanyMemberAddIn(BaseModel):
    email: EmailStr


class CompanyMemberUpdateIn(BaseModel):
    role: Optional[MemberRole] = None
    status: Optional[MemberStatus] = None


class CompanyMemberOut(BaseModel):
    id: UUID
    user_id: UUID
    email: EmailStr
    name: Optional[str] = None
    role: MemberRole
    status: MemberStatus
    joined_at: datetime
    removed_at: Optional[datetime] = None


class RuleSetSystemPromptOut(BaseModel):
    rule_set_id: UUID
    system_prompt: Optional[str] = None


class CompanySystemPromptUpdateIn(BaseModel):
    system_prompt: Optional[str] = PydanticField(default=None, max_length=4000)


# Backward-compatible aliases to keep internal imports stable.
CompanyCreateIn = RuleSetCreateIn
CompanyOut = RuleSetOut
CompanySystemPromptOut = RuleSetSystemPromptOut
