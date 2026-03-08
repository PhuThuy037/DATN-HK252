from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel
from uuid import UUID, uuid4

from app.common.bases import TimestampMixin


class UserRuleOverride(TimestampMixin, SQLModel, table=True):
    __tablename__ = "user_rule_overrides"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "stable_key", name="uq_user_rule_overrides_user_stable"
        ),
        Index("ix_user_rule_overrides_user_enabled", "user_id", "enabled"),
        Index("ix_user_rule_overrides_stable_key", "stable_key"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(
        sa_column=sa.Column(
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    stable_key: str = Field(nullable=False, index=True)

    enabled: bool = Field(
        default=True,
        sa_column=sa.Column(
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
