# app/rag/models/context_term.py

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import SQLModel, Field


class ContextTerm(SQLModel, table=True):
    __tablename__ = "context_terms"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    company_id: Optional[UUID] = Field(
        default=None,
        foreign_key="companies.id",
        index=True,
    )

    entity_type: str = Field(index=True)  # PHONE, CCCD, TAX_ID...
    term: str = Field(index=True)
    lang: str = Field(default="vi", index=True)

    weight: float = Field(default=1.0)  # context boost
    window_1: int = Field(default=60)  # outer window
    window_2: int = Field(default=20)  # inner window

    enabled: bool = Field(default=True)

    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
    )

