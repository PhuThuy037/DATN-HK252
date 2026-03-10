from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class RuleChangeLog(SQLModel, table=True):
    __tablename__ = "rule_change_logs"
    __table_args__ = (
        Index("ix_rule_change_logs_company_created", "company_id", "created_at"),
        Index("ix_rule_change_logs_rule_created", "rule_id", "created_at"),
        Index("ix_rule_change_logs_actor_created", "actor_user_id", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    company_id: UUID = Field(foreign_key="companies.id", nullable=False, index=True)
    rule_id: UUID = Field(foreign_key="rules.id", nullable=False, index=True)
    actor_user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)

    action: str = Field(
        sa_column=sa.Column(sa.String(64), nullable=False, index=True)
    )
    changed_fields: list[str] = Field(sa_column=sa.Column(JSONB, nullable=False))
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
            index=True,
        )
    )


