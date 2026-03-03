from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field


class PolicyChunk(SQLModel, table=True):
    __tablename__ = "policy_chunks"

    __table_args__ = (
        # 1 doc có nhiều chunk, đảm bảo thứ tự chunk unique
        UniqueConstraint("document_id", "chunk_index", name="uq_policy_chunk_order"),
        # optional: dedup theo nội dung trong 1 document
        UniqueConstraint("document_id", "content_hash", name="uq_policy_chunk_hash"),
        # index phục vụ query load chunks theo doc
        sa.Index("ix_policy_chunks_doc_idx", "document_id", "chunk_index"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    document_id: UUID = Field(
        foreign_key="policy_documents.id",
        nullable=False,
        index=True,
    )

    company_id: Optional[UUID] = Field(
        default=None,
        foreign_key="companies.id",
        index=True,
    )

    chunk_index: int = Field(index=True)
    content: str

    content_hash: str = Field(
        sa_type=sa.String(64),
        sa_column_kwargs={"nullable": False, "index": True},
    )

    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
    )