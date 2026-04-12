"""add rule match_mode

Revision ID: c6b1e92f4a77
Revises: a1c9f4d6e2b3
Create Date: 2026-04-10 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c6b1e92f4a77"
down_revision: Union[str, Sequence[str], None] = "a1c9f4d6e2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    match_mode_enum = sa.Enum(
        "strict_keyword",
        "keyword_plus_semantic",
        name="match_mode",
    )
    match_mode_enum.create(bind, checkfirst=True)

    op.add_column(
        "rules",
        sa.Column(
            "match_mode",
            match_mode_enum,
            nullable=False,
            server_default=sa.text("'strict_keyword'::match_mode"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    op.drop_column("rules", "match_mode")
    sa.Enum(
        "strict_keyword",
        "keyword_plus_semantic",
        name="match_mode",
    ).drop(bind, checkfirst=True)
