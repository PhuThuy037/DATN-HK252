from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import SQLModel, Field


class PolicyDocument(SQLModel, table=True):
    __tablename__ = "policy_documents"

    __table_args__ = (
        sa.Index("ix_policy_documents_company_enabled", "company_id", "enabled"),
        sa.Index("ix_policy_documents_company_stable_key", "company_id", "stable_key"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    company_id: Optional[UUID] = Field(
        default=None,
        foreign_key="companies.id",
        index=True,
    )

    stable_key: str = Field(
        sa_type=sa.String(200),
        sa_column_kwargs={"nullable": False},
    )

    title: str
    content: str
    content_hash: str = Field(
        sa_type=sa.String(64),
        sa_column_kwargs={"nullable": False},
    )
    version: int = Field(default=1, ge=1)

    doc_type: str = Field(index=True)  # policy, guideline, injection_knowledge...
    enabled: bool = Field(default=True)

    created_by: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
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
    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )


