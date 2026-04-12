"""add rule context term links

Revision ID: d91f6e2ab314
Revises: c6b1e92f4a77
Create Date: 2026-04-10 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d91f6e2ab314"
down_revision: Union[str, Sequence[str], None] = "c6b1e92f4a77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rule_context_term_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("context_term_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["context_term_id"], ["context_terms.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["rules.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rule_id",
            "context_term_id",
            "source",
            name="uq_rule_context_term_links_rule_term_source",
        ),
    )
    op.create_index(
        "ix_rule_context_term_links_rule_source",
        "rule_context_term_links",
        ["rule_id", "source"],
        unique=False,
    )
    op.create_index(
        "ix_rule_context_term_links_context_term_id",
        "rule_context_term_links",
        ["context_term_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_rule_context_term_links_context_term_id",
        table_name="rule_context_term_links",
    )
    op.drop_index(
        "ix_rule_context_term_links_rule_source",
        table_name="rule_context_term_links",
    )
    op.drop_table("rule_context_term_links")
