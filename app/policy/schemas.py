from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field as PydanticField


class PolicyIngestStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"


class PolicyDocumentOut(BaseModel):
    id: UUID
    company_id: Optional[UUID]
    stable_key: str
    title: str
    doc_type: str
    content_hash: str
    version: int
    enabled: bool
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


class PolicyDocumentToggleEnabledIn(BaseModel):
    enabled: bool


class PolicyIngestItemIn(BaseModel):
    stable_key: str = PydanticField(min_length=1, max_length=200)
    title: str = PydanticField(min_length=1, max_length=300)
    content: str = PydanticField(min_length=1)
    doc_type: str = PydanticField(default="policy", min_length=1, max_length=100)
    enabled: bool = True


class PolicyIngestJobCreateIn(BaseModel):
    items: list[PolicyIngestItemIn] = PydanticField(min_length=1, max_length=200)


class PolicyIngestJobItemOut(BaseModel):
    id: UUID
    stable_key: str
    title: str
    doc_type: str
    content_hash: str
    enabled: bool
    status: PolicyIngestStatus
    document_id: Optional[UUID]
    error_message: Optional[str]
    attempt: int
    created_at: datetime
    updated_at: datetime


class PolicyIngestJobOut(BaseModel):
    id: UUID
    company_id: UUID
    requested_by: UUID
    retry_of_job_id: Optional[UUID]
    status: PolicyIngestStatus
    total_items: int
    success_items: int
    failed_items: int
    skipped_items: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class PolicyIngestJobDetailOut(PolicyIngestJobOut):
    error_json: Optional[dict]
    items: list[PolicyIngestJobItemOut]
