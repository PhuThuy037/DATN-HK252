from typing import Any, Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.common.bases import TimestampMixin
from app.common.enums import RagMode, RuleAction, RuleScope, RuleSeverity


class Rule(TimestampMixin, SQLModel, table=True):
    __tablename__ = "rules"
    __table_args__ = (
        Index("ix_rules_company_enabled_scope", "company_id", "enabled", "scope"),
        Index(
            "ix_rules_company_enabled_scope_priority",
            "company_id",
            "enabled",
            "scope",
            "priority",
        ),
        Index("ix_rules_enabled_scope", "enabled", "scope"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # NULL = global rule, NOT NULL = company rule
    company_id: Optional[UUID] = Field(default=None, foreign_key="companies.id")

    name: str = Field(nullable=False, index=True)
    description: Optional[str] = Field(default=None)

    scope: RuleScope = Field(
        sa_column=sa.Column(
            sa.Enum(RuleScope, name="rule_scope", native_enum=True),
            nullable=False,
        )
    )

    # JSONB conditions
    conditions: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))

    conditions_version: int = Field(
        default=1,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default="1"),
    )

    action: RuleAction = Field(
        sa_column=sa.Column(
            sa.Enum(RuleAction, name="rule_action", native_enum=True),
            nullable=False,
        )
    )

    severity: RuleSeverity = Field(
        default=RuleSeverity.medium,
        sa_column=sa.Column(
            sa.Enum(RuleSeverity, name="rule_severity", native_enum=True),
            nullable=False,
            server_default=RuleSeverity.medium.value,
        ),
    )

    priority: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default="0"),
    )

    rag_mode: RagMode = Field(
        default=RagMode.off,
        sa_column=sa.Column(
            sa.Enum(RagMode, name="rag_mode", native_enum=True),
            nullable=False,
            server_default=RagMode.off.value,
        ),
    )

    enabled: bool = Field(
        default=True,
        sa_column=sa.Column(
            sa.Boolean, nullable=False, server_default=sa.text("true"), index=True
        ),
    )

    created_by: UUID = Field(foreign_key="users.id", nullable=False)

    # relationships
    company: Optional["Company"] = Relationship(back_populates="rules")
    creator: "User" = Relationship(back_populates="created_rules")
    embeddings: list["RuleEmbedding"] = Relationship(back_populates="rule")
