"""add system role to users

Revision ID: a1c9f4d6e2b3
Revises: 8d4c2a1e9b60
Create Date: 2026-04-08 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c9f4d6e2b3"
down_revision: Union[str, Sequence[str], None] = "8d4c2a1e9b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    system_role = sa.Enum("admin", "user", name="system_role")
    bind = op.get_bind()
    system_role.create(bind, checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "role",
            system_role,
            nullable=False,
            server_default="user",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "role")
    system_role = sa.Enum("admin", "user", name="system_role")
    bind = op.get_bind()
    system_role.drop(bind, checkfirst=True)
