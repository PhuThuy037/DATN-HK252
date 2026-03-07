"""add rule suggestions and suggestion logs tables

Revision ID: 24c1f5d987aa
Revises: 9b7d1c2e4a11
Create Date: 2026-03-07 20:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "24c1f5d987aa"
down_revision: Union[str, Sequence[str], None] = "9b7d1c2e4a11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rule_suggestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("nl_input", sa.Text(), nullable=False),
        sa.Column("draft_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("approve_reason", sa.Text(), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column(
            "applied_result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("rejected_by", sa.Uuid(), nullable=True),
        sa.Column("applied_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["rejected_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["applied_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rule_suggestions_company_status",
        "rule_suggestions",
        ["company_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_rule_suggestions_company_created",
        "rule_suggestions",
        ["company_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_rule_suggestions_company_dedupe",
        "rule_suggestions",
        ["company_id", "dedupe_key"],
        unique=False,
    )
    op.create_index(op.f("ix_rule_suggestions_company_id"), "rule_suggestions", ["company_id"], unique=False)
    op.create_index(op.f("ix_rule_suggestions_created_by"), "rule_suggestions", ["created_by"], unique=False)
    op.create_index(op.f("ix_rule_suggestions_status"), "rule_suggestions", ["status"], unique=False)
    op.create_index(op.f("ix_rule_suggestions_type"), "rule_suggestions", ["type"], unique=False)
    op.create_index(op.f("ix_rule_suggestions_approved_by"), "rule_suggestions", ["approved_by"], unique=False)
    op.create_index(op.f("ix_rule_suggestions_rejected_by"), "rule_suggestions", ["rejected_by"], unique=False)
    op.create_index(op.f("ix_rule_suggestions_applied_by"), "rule_suggestions", ["applied_by"], unique=False)
    op.create_index(op.f("ix_rule_suggestions_expires_at"), "rule_suggestions", ["expires_at"], unique=False)

    op.create_table(
        "rule_suggestion_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("suggestion_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["suggestion_id"], ["rule_suggestions.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rule_suggestion_logs_suggestion_created",
        "rule_suggestion_logs",
        ["suggestion_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_rule_suggestion_logs_company_created",
        "rule_suggestion_logs",
        ["company_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rule_suggestion_logs_suggestion_id"),
        "rule_suggestion_logs",
        ["suggestion_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rule_suggestion_logs_company_id"),
        "rule_suggestion_logs",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rule_suggestion_logs_actor_user_id"),
        "rule_suggestion_logs",
        ["actor_user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_rule_suggestion_logs_actor_user_id"), table_name="rule_suggestion_logs")
    op.drop_index(op.f("ix_rule_suggestion_logs_company_id"), table_name="rule_suggestion_logs")
    op.drop_index(op.f("ix_rule_suggestion_logs_suggestion_id"), table_name="rule_suggestion_logs")
    op.drop_index("ix_rule_suggestion_logs_company_created", table_name="rule_suggestion_logs")
    op.drop_index("ix_rule_suggestion_logs_suggestion_created", table_name="rule_suggestion_logs")
    op.drop_table("rule_suggestion_logs")

    op.drop_index(op.f("ix_rule_suggestions_expires_at"), table_name="rule_suggestions")
    op.drop_index(op.f("ix_rule_suggestions_applied_by"), table_name="rule_suggestions")
    op.drop_index(op.f("ix_rule_suggestions_rejected_by"), table_name="rule_suggestions")
    op.drop_index(op.f("ix_rule_suggestions_approved_by"), table_name="rule_suggestions")
    op.drop_index(op.f("ix_rule_suggestions_type"), table_name="rule_suggestions")
    op.drop_index(op.f("ix_rule_suggestions_status"), table_name="rule_suggestions")
    op.drop_index(op.f("ix_rule_suggestions_created_by"), table_name="rule_suggestions")
    op.drop_index(op.f("ix_rule_suggestions_company_id"), table_name="rule_suggestions")
    op.drop_index("ix_rule_suggestions_company_dedupe", table_name="rule_suggestions")
    op.drop_index("ix_rule_suggestions_company_created", table_name="rule_suggestions")
    op.drop_index("ix_rule_suggestions_company_status", table_name="rule_suggestions")
    op.drop_table("rule_suggestions")
