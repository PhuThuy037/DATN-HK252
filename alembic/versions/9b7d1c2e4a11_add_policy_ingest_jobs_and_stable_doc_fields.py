"""add policy ingest jobs and stable policy document fields

Revision ID: 9b7d1c2e4a11
Revises: 7f2b1e6c9a10
Create Date: 2026-03-07 18:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9b7d1c2e4a11"
down_revision: Union[str, Sequence[str], None] = "7f2b1e6c9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "policy_documents",
        sa.Column("stable_key", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "policy_documents",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "policy_documents",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "policy_documents",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "policy_documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        "UPDATE policy_documents "
        "SET stable_key = CONCAT('legacy.', id::text) "
        "WHERE stable_key IS NULL"
    )
    op.execute(
        "UPDATE policy_documents "
        "SET content_hash = md5(content) "
        "WHERE content_hash IS NULL"
    )
    op.alter_column("policy_documents", "stable_key", nullable=False)
    op.alter_column("policy_documents", "content_hash", nullable=False)

    op.create_index(
        "ix_policy_documents_company_stable_key",
        "policy_documents",
        ["company_id", "stable_key"],
        unique=False,
    )
    op.create_index(
        "uq_policy_documents_global_stable_key",
        "policy_documents",
        ["stable_key"],
        unique=True,
        postgresql_where=sa.text("company_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_policy_documents_company_stable_key",
        "policy_documents",
        ["company_id", "stable_key"],
        unique=True,
        postgresql_where=sa.text("company_id IS NOT NULL AND deleted_at IS NULL"),
    )

    op.create_table(
        "policy_ingest_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("retry_of_job_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("success_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("skipped_items", sa.Integer(), nullable=False),
        sa.Column(
            "payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["retry_of_job_id"], ["policy_ingest_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_policy_ingest_jobs_company_created",
        "policy_ingest_jobs",
        ["company_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_policy_ingest_jobs_company_status",
        "policy_ingest_jobs",
        ["company_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_ingest_jobs_company_id"),
        "policy_ingest_jobs",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_ingest_jobs_requested_by"),
        "policy_ingest_jobs",
        ["requested_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_ingest_jobs_retry_of_job_id"),
        "policy_ingest_jobs",
        ["retry_of_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_ingest_jobs_status"),
        "policy_ingest_jobs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "policy_ingest_job_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("stable_key", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["policy_documents.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["policy_ingest_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "stable_key", name="uq_policy_ingest_job_item_key"),
    )
    op.create_index(
        "ix_policy_ingest_job_items_job_status",
        "policy_ingest_job_items",
        ["job_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_policy_ingest_job_items_company_status",
        "policy_ingest_job_items",
        ["company_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_ingest_job_items_company_id"),
        "policy_ingest_job_items",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_ingest_job_items_document_id"),
        "policy_ingest_job_items",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_ingest_job_items_job_id"),
        "policy_ingest_job_items",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_ingest_job_items_status"),
        "policy_ingest_job_items",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_policy_ingest_job_items_status"), table_name="policy_ingest_job_items")
    op.drop_index(op.f("ix_policy_ingest_job_items_job_id"), table_name="policy_ingest_job_items")
    op.drop_index(
        op.f("ix_policy_ingest_job_items_document_id"),
        table_name="policy_ingest_job_items",
    )
    op.drop_index(op.f("ix_policy_ingest_job_items_company_id"), table_name="policy_ingest_job_items")
    op.drop_index(
        "ix_policy_ingest_job_items_company_status",
        table_name="policy_ingest_job_items",
    )
    op.drop_index(
        "ix_policy_ingest_job_items_job_status",
        table_name="policy_ingest_job_items",
    )
    op.drop_table("policy_ingest_job_items")

    op.drop_index(op.f("ix_policy_ingest_jobs_status"), table_name="policy_ingest_jobs")
    op.drop_index(op.f("ix_policy_ingest_jobs_retry_of_job_id"), table_name="policy_ingest_jobs")
    op.drop_index(op.f("ix_policy_ingest_jobs_requested_by"), table_name="policy_ingest_jobs")
    op.drop_index(op.f("ix_policy_ingest_jobs_company_id"), table_name="policy_ingest_jobs")
    op.drop_index("ix_policy_ingest_jobs_company_status", table_name="policy_ingest_jobs")
    op.drop_index("ix_policy_ingest_jobs_company_created", table_name="policy_ingest_jobs")
    op.drop_table("policy_ingest_jobs")

    op.drop_index("uq_policy_documents_company_stable_key", table_name="policy_documents")
    op.drop_index("uq_policy_documents_global_stable_key", table_name="policy_documents")
    op.drop_index("ix_policy_documents_company_stable_key", table_name="policy_documents")

    op.drop_column("policy_documents", "deleted_at")
    op.drop_column("policy_documents", "updated_at")
    op.drop_column("policy_documents", "version")
    op.drop_column("policy_documents", "content_hash")
    op.drop_column("policy_documents", "stable_key")
