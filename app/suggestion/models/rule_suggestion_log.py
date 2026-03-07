from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class RuleSuggestionLog(SQLModel, table=True):
    __tablename__ = "rule_suggestion_logs"

    __table_args__ = (
        sa.Index("ix_rule_suggestion_logs_suggestion_created", "suggestion_id", "created_at"),
        sa.Index("ix_rule_suggestion_logs_company_created", "company_id", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    suggestion_id: UUID = Field(foreign_key="rule_suggestions.id", nullable=False, index=True)
    company_id: UUID = Field(foreign_key="companies.id", nullable=False, index=True)
    actor_user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)

    action: str = Field(sa_type=sa.String(64), sa_column_kwargs={"nullable": False})
    reason: Optional[str] = Field(
        default=None,
        sa_column=sa.Column(sa.Text(), nullable=True),
    )
    before_json: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=sa.Column(JSONB, nullable=True),
    )
    after_json: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=sa.Column(JSONB, nullable=True),
    )

    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
    )
