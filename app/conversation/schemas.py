from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field as PydanticField

from app.common.enums import MessageInputType, MessageRole


class ConversationCreatePersonalIn(BaseModel):
    title: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None


class ConversationCreateCompanyIn(BaseModel):
    title: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None


class ConversationOut(BaseModel):
    id: UUID
    user_id: UUID
    company_id: Optional[UUID]
    title: Optional[str]
    model_name: Optional[str]
    temperature: Optional[float]
    last_sequence_number: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageCreateIn(BaseModel):
    content: str = PydanticField(min_length=1)
    input_type: MessageInputType = MessageInputType.user_input


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    sequence_number: int
    input_type: MessageInputType
    content: Optional[str]
    content_hash: Optional[str]
    content_masked: Optional[str]
    scan_status: str
    pre_rag_action: Optional[str]
    final_action: Optional[str]
    risk_score: Optional[float]
    ambiguous: bool
    created_at: datetime
    matched_rule_ids: Optional[list[str]] = None
    entities_json: Optional[dict[str, Any]] = None
    rag_evidence_json: Optional[dict[str, Any]] = None
    latency_ms: Optional[int] = None
    blocked: bool = False
    blocked_reason: Optional[str] = None
    
    class Config:
        from_attributes = True