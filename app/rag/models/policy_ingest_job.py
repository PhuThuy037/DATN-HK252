from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class PolicyIngestJob(SQLModel, table=True):
    __tablename__ = "policy_ingest_jobs"

    __table_args__ = (
        sa.Index("ix_policy_ingest_jobs_company_created", "company_id", "created_at"),
        sa.Index("ix_policy_ingest_jobs_company_status", "company_id", "status"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    company_id: UUID = Field(foreign_key="companies.id", nullable=False, index=True)
    requested_by: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    retry_of_job_id: Optional[UUID] = Field(
        default=None,
        foreign_key="policy_ingest_jobs.id",
        index=True,
    )

    status: str = Field(default="pending", index=True)  # pending|running|success|failed

    total_items: int = Field(default=0)
    success_items: int = Field(default=0)
    failed_items: int = Field(default=0)
    skipped_items: int = Field(default=0)

    payload_json: dict[str, Any] = Field(sa_column=sa.Column(JSONB, nullable=False))
    error_json: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=sa.Column(JSONB, nullable=True),
    )

    started_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    finished_at: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
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


