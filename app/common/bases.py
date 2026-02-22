from datetime import datetime
from sqlmodel import Field
import sqlalchemy as sa


class TimestampMixin:
    created_at: datetime = Field(
        default=None,
        sa_type=sa.DateTime(timezone=True),
        sa_column_kwargs={"server_default": sa.func.now()},
        nullable=False,
    )
    updated_at: datetime = Field(
        default=None,
        sa_type=sa.DateTime(timezone=True),
        sa_column_kwargs={"server_default": sa.func.now(), "onupdate": sa.func.now()},
        nullable=False,
    )
