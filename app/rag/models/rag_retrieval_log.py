# app/rag/models/rag_retrieval_log.py

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


class RagRetrievalLog(SQLModel, table=True):
    __tablename__ = "rag_retrieval_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    message_id: Optional[UUID] = Field(
        default=None,
        foreign_key="messages.id",
        index=True,
    )

    query: str
    top_k: int

    results_json: Dict[str, Any] = Field(sa_column=sa.Column(JSONB, nullable=False))

    latency_ms: int

    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
    )