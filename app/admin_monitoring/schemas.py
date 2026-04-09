from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from app.conversation.schemas import MessageDetailOut, MessagesPageMeta


class AdminConversationListItemOut(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str
    user_name: Optional[str] = None
    rule_set_id: Optional[UUID] = None
    title: Optional[str] = None
    status: str
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    last_sequence_number: int
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    message_count: int = 0
    block_count: int = 0
    mask_count: int = 0
    has_sensitive_action: bool = False


class AdminConversationDetailOut(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str
    user_name: Optional[str] = None
    rule_set_id: Optional[UUID] = None
    title: Optional[str] = None
    status: str
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    last_sequence_number: int
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    block_count: int = 0
    mask_count: int = 0


class AdminConversationMessagesPageOut(BaseModel):
    items: list[MessageDetailOut]
    page: MessagesPageMeta


class AdminBlockMaskLogOut(BaseModel):
    message_id: UUID
    conversation_id: UUID
    user_id: UUID
    user_email: str
    user_name: Optional[str] = None
    conversation_title: Optional[str] = None
    role: str
    input_type: Optional[str] = None
    action: str
    summary: Optional[str] = None
    content: Optional[str] = None
    content_masked: Optional[str] = None
    matched_rule_ids: Optional[list[str]] = None
    matched_rules: Optional[list[dict[str, Any]]] = None
    risk_score: Optional[float] = None
    blocked: bool = False
    created_at: datetime


class AdminRagRetrievalLogOut(BaseModel):
    id: UUID
    message_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    query: str
    top_k: int
    result_count: int = 0
    latency_ms: int
    created_at: datetime


class AdminAuditLogOut(BaseModel):
    id: UUID
    rule_set_id: UUID
    rule_id: UUID
    actor_user_id: UUID
    actor_email: Optional[str] = None
    actor_name: Optional[str] = None
    action: str
    changed_fields: list[str]
    before_json: Optional[dict[str, Any]] = None
    after_json: Optional[dict[str, Any]] = None
    created_at: datetime
