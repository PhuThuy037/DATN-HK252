"""add user rule overrides for personal scope

Revision ID: 6a1d4f2c8b90
Revises: 24c1f5d987aa
Create Date: 2026-03-08 20:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6a1d4f2c8b90"
down_revision: Union[str, Sequence[str], None] = "24c1f5d987aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_rule_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("stable_key", sa.String(), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "stable_key", name="uq_user_rule_overrides_user_stable"
        ),
    )
    op.create_index(
        "ix_user_rule_overrides_user_id",
        "user_rule_overrides",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_rule_overrides_stable_key",
        "user_rule_overrides",
        ["stable_key"],
        unique=False,
    )
    op.create_index(
        "ix_user_rule_overrides_user_enabled",
        "user_rule_overrides",
        ["user_id", "enabled"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_user_rule_overrides_user_enabled", table_name="user_rule_overrides"
    )
    op.drop_index("ix_user_rule_overrides_stable_key", table_name="user_rule_overrides")
    op.drop_index("ix_user_rule_overrides_user_id", table_name="user_rule_overrides")
    op.drop_table("user_rule_overrides")
