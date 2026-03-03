# app/rag/models/policy_chunk_embedding.py

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, UniqueConstraint
from sqlmodel import SQLModel, Field


class PolicyChunkEmbedding(SQLModel, table=True):
    __tablename__ = "policy_chunk_embeddings"

    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "model_name",
            name="uq_policy_chunk_embedding_model",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    chunk_id: UUID = Field(
        foreign_key="policy_chunks.id",
        nullable=False,
        index=True,
    )

    model_name: str = Field(index=True)

    embedding: Any = Field(sa_column=Column(Vector(1024), nullable=False))

    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
    )