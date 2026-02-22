from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class RuleEmbedding(SQLModel, table=True):
    __tablename__ = "rule_embeddings"
    __table_args__ = (
        UniqueConstraint("rule_id", "model_name", name="uq_rule_embeddings_rule_model"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    rule_id: UUID = Field(foreign_key="rules.id", nullable=False)

    content: str = Field(nullable=False)

    content_hash: str = Field(
        sa_type=sa.String(64),
        sa_column_kwargs={"nullable": False, "unique": True, "index": True},
    )

    embedding: Any = Field(
        sa_column=Column(Vector(1536), nullable=False),  # dims example
    )

    model_name: str = Field(nullable=False)

    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # relationships
    rule: "Rule" = Relationship(back_populates="embeddings")
