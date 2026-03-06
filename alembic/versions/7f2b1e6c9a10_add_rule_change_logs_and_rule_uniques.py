"""add rule change logs and unique stable_key indexes

Revision ID: 7f2b1e6c9a10
Revises: 3c1f7ea46d9b
Create Date: 2026-03-06 17:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7f2b1e6c9a10"
down_revision: Union[str, Sequence[str], None] = "3c1f7ea46d9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "uq_rules_global_stable_key",
        "rules",
        ["stable_key"],
        unique=True,
        postgresql_where=sa.text("company_id IS NULL"),
    )
    op.create_index(
        "uq_rules_company_stable_key",
        "rules",
        ["company_id", "stable_key"],
        unique=True,
        postgresql_where=sa.text("company_id IS NOT NULL"),
    )

    op.create_table(
        "rule_change_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("changed_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["rules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rule_change_logs_actor_created",
        "rule_change_logs",
        ["actor_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_rule_change_logs_company_created",
        "rule_change_logs",
        ["company_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_rule_change_logs_rule_created",
        "rule_change_logs",
        ["rule_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rule_change_logs_action"),
        "rule_change_logs",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rule_change_logs_actor_user_id"),
        "rule_change_logs",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rule_change_logs_company_id"),
        "rule_change_logs",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rule_change_logs_created_at"),
        "rule_change_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rule_change_logs_rule_id"),
        "rule_change_logs",
        ["rule_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_rule_change_logs_rule_id"), table_name="rule_change_logs")
    op.drop_index(op.f("ix_rule_change_logs_created_at"), table_name="rule_change_logs")
    op.drop_index(op.f("ix_rule_change_logs_company_id"), table_name="rule_change_logs")
    op.drop_index(op.f("ix_rule_change_logs_actor_user_id"), table_name="rule_change_logs")
    op.drop_index(op.f("ix_rule_change_logs_action"), table_name="rule_change_logs")
    op.drop_index("ix_rule_change_logs_rule_created", table_name="rule_change_logs")
    op.drop_index("ix_rule_change_logs_company_created", table_name="rule_change_logs")
    op.drop_index("ix_rule_change_logs_actor_created", table_name="rule_change_logs")
    op.drop_table("rule_change_logs")

    op.drop_index("uq_rules_company_stable_key", table_name="rules")
    op.drop_index("uq_rules_global_stable_key", table_name="rules")
