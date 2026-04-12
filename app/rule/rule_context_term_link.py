from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel


class RuleContextTermLink(SQLModel, table=True):
    __tablename__ = "rule_context_term_links"
    __table_args__ = (
        UniqueConstraint(
            "rule_id",
            "context_term_id",
            "source",
            name="uq_rule_context_term_links_rule_term_source",
        ),
        Index("ix_rule_context_term_links_rule_source", "rule_id", "source"),
        Index("ix_rule_context_term_links_context_term_id", "context_term_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    rule_id: UUID = Field(foreign_key="rules.id", nullable=False)
    context_term_id: UUID = Field(foreign_key="context_terms.id", nullable=False)
    source: str = Field(sa_type=sa.String(16), nullable=False)

    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
    )
