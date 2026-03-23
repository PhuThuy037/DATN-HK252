"""add company rule overrides and rule deletion flag

Revision ID: 8d4c2a1e9b60
Revises: 6a1d4f2c8b90
Create Date: 2026-03-23 23:40:00.000000

"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d4c2a1e9b60"
down_revision: Union[str, Sequence[str], None] = "6a1d4f2c8b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "rules",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.create_table(
        "company_rule_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("stable_key", sa.String(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "stable_key",
            name="uq_company_rule_overrides_company_stable",
        ),
    )
    op.create_index(
        "ix_company_rule_overrides_company_id",
        "company_rule_overrides",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_company_rule_overrides_stable_key",
        "company_rule_overrides",
        ["stable_key"],
        unique=False,
    )
    op.create_index(
        "ix_company_rule_overrides_company_enabled",
        "company_rule_overrides",
        ["company_id", "enabled"],
        unique=False,
    )

    bind = op.get_bind()
    legacy_rows = bind.execute(
        sa.text(
            """
            SELECT r.company_id, r.stable_key, r.enabled
            FROM rules r
            WHERE r.company_id IS NOT NULL
              AND EXISTS (
                SELECT 1
                FROM rules g
                WHERE g.company_id IS NULL
                  AND g.stable_key = r.stable_key
              )
            """
        )
    ).fetchall()

    if legacy_rows:
        now = datetime.now(timezone.utc)
        insert_stmt = sa.text(
            """
            INSERT INTO company_rule_overrides
                (id, company_id, stable_key, enabled, created_at, updated_at)
            VALUES
                (:id, :company_id, :stable_key, :enabled, :created_at, :updated_at)
            ON CONFLICT (company_id, stable_key)
            DO UPDATE SET
                enabled = EXCLUDED.enabled,
                updated_at = EXCLUDED.updated_at
            """
        )
        for row in legacy_rows:
            bind.execute(
                insert_stmt,
                {
                    "id": str(uuid4()),
                    "company_id": row[0],
                    "stable_key": row[1],
                    "enabled": bool(row[2]),
                    "created_at": now,
                    "updated_at": now,
                },
            )

        bind.execute(
            sa.text(
                """
                UPDATE rules r
                SET is_deleted = true
                WHERE r.company_id IS NOT NULL
                  AND EXISTS (
                    SELECT 1
                    FROM rules g
                    WHERE g.company_id IS NULL
                      AND g.stable_key = r.stable_key
                  )
                """
            )
        )

    op.drop_index("uq_rules_global_stable_key", table_name="rules")
    op.drop_index("uq_rules_company_stable_key", table_name="rules")

    op.create_index(
        "uq_rules_global_stable_key",
        "rules",
        ["stable_key"],
        unique=True,
        postgresql_where=sa.text("company_id IS NULL AND is_deleted = false"),
    )
    op.create_index(
        "uq_rules_company_stable_key",
        "rules",
        ["company_id", "stable_key"],
        unique=True,
        postgresql_where=sa.text("company_id IS NOT NULL AND is_deleted = false"),
    )
    op.create_index(
        "ix_rules_company_deleted_scope",
        "rules",
        ["company_id", "is_deleted", "scope"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_rules_company_deleted_scope", table_name="rules")
    op.drop_index("uq_rules_company_stable_key", table_name="rules")
    op.drop_index("uq_rules_global_stable_key", table_name="rules")

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

    op.drop_index(
        "ix_company_rule_overrides_company_enabled",
        table_name="company_rule_overrides",
    )
    op.drop_index("ix_company_rule_overrides_stable_key", table_name="company_rule_overrides")
    op.drop_index("ix_company_rule_overrides_company_id", table_name="company_rule_overrides")
    op.drop_table("company_rule_overrides")

    op.drop_column("rules", "is_deleted")
