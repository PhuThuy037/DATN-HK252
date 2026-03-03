# app/rag/models/context_term_embedding.py

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, UniqueConstraint
from sqlmodel import SQLModel, Field


class ContextTermEmbedding(SQLModel, table=True):
    __tablename__ = "context_term_embeddings"

    __table_args__ = (
        UniqueConstraint(
            "context_term_id",
            "model_name",
            name="uq_context_term_embedding_model",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    context_term_id: UUID = Field(
        foreign_key="context_terms.id",
        nullable=False,
        index=True,
    )

    model_name: str = Field(index=True)

    embedding: Any = Field(sa_column=Column(Vector(768), nullable=False))

    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
    )