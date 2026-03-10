from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class PolicyIngestJobItem(SQLModel, table=True):
    __tablename__ = "policy_ingest_job_items"

    __table_args__ = (
        sa.UniqueConstraint("job_id", "stable_key", name="uq_policy_ingest_job_item_key"),
        sa.Index("ix_policy_ingest_job_items_job_status", "job_id", "status"),
        sa.Index("ix_policy_ingest_job_items_company_status", "company_id", "status"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    job_id: UUID = Field(foreign_key="policy_ingest_jobs.id", nullable=False, index=True)
    company_id: UUID = Field(foreign_key="companies.id", nullable=False, index=True)

    stable_key: str = Field(sa_type=sa.String(200), sa_column_kwargs={"nullable": False})
    title: str
    doc_type: str = Field(default="policy")
    content: str
    content_hash: str = Field(sa_type=sa.String(64), sa_column_kwargs={"nullable": False})
    enabled: bool = Field(default=True)

    status: str = Field(default="pending", index=True)  # pending|running|success|failed|skipped
    document_id: Optional[UUID] = Field(
        default=None,
        foreign_key="policy_documents.id",
        index=True,
    )
    error_message: Optional[str] = Field(
        default=None,
        sa_column=sa.Column(sa.Text(), nullable=True),
    )
    attempt: int = Field(default=1, ge=1)

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


