# app/rag/models/policy_document.py

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import SQLModel, Field


class PolicyDocument(SQLModel, table=True):
    __tablename__ = "policy_documents"

    __table_args__ = (
        sa.Index("ix_policy_documents_company_enabled", "company_id", "enabled"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    company_id: Optional[UUID] = Field(
        default=None,
        foreign_key="companies.id",
        index=True,
    )

    title: str
    content: str

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