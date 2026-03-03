"""add company system_prompt column

Revision ID: 3c1f7ea46d9b
Revises: 0f8e0583c04e
Create Date: 2026-03-03 22:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3c1f7ea46d9b"
down_revision: Union[str, Sequence[str], None] = "0f8e0583c04e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("companies", sa.Column("system_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("companies", "system_prompt")
