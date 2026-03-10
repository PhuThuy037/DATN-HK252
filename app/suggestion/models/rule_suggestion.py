from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class RuleSuggestion(SQLModel, table=True):
    __tablename__ = "rule_suggestions"

    __table_args__ = (
        sa.Index("ix_rule_suggestions_company_status", "company_id", "status"),
        sa.Index("ix_rule_suggestions_company_created", "company_id", "created_at"),
        sa.Index("ix_rule_suggestions_company_dedupe", "company_id", "dedupe_key"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    company_id: UUID = Field(foreign_key="companies.id", nullable=False, index=True)
    created_by: UUID = Field(foreign_key="users.id", nullable=False, index=True)

    status: str = Field(default="draft", index=True)  # draft|approved|applied|rejected|expired|failed
    type: str = Field(default="rule_with_context", index=True)
    version: int = Field(default=1, ge=1)

    nl_input: str = Field(sa_column=sa.Column(sa.Text(), nullable=False))
    draft_json: dict[str, Any] = Field(sa_column=sa.Column(JSONB, nullable=False))
    dedupe_key: str = Field(
        sa_type=sa.String(64),
        sa_column_kwargs={"nullable": False},
    )

    approve_reason: Optional[str] = Field(
        default=None,
        sa_column=sa.Column(sa.Text(), nullable=True),
    )
    reject_reason: Optional[str] = Field(
        default=None,
        sa_column=sa.Column(sa.Text(), nullable=True),
    )
    applied_result_json: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=sa.Column(JSONB, nullable=True),
    )

    approved_by: Optional[UUID] = Field(default=None, foreign_key="users.id", index=True)
    rejected_by: Optional[UUID] = Field(default=None, foreign_key="users.id", index=True)
    applied_by: Optional[UUID] = Field(default=None, foreign_key="users.id", index=True)

    approved_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    rejected_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    applied_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True, index=True),
    )

    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
    )
    updated_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        )
    )


