from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import Index
from sqlmodel import Field, Relationship, SQLModel

from app.common.enums import EntitySource


class PromptEntity(SQLModel, table=True):
    __tablename__ = "prompt_entities"
    __table_args__ = (
        Index("ix_prompt_entities_message", "message_id"),
        Index("ix_prompt_entities_type", "entity_type"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    message_id: UUID = Field(foreign_key="messages.id", nullable=False)

    source: EntitySource = Field(
        sa_column=sa.Column(
            sa.Enum(
                EntitySource,
                name="entity_source",  # ✅ DB enum type name
                native_enum=True,
            ),
            nullable=False,
        )
    )

    entity_type: str = Field(nullable=False)

    start_index: Optional[int] = Field(default=None)
    end_index: Optional[int] = Field(default=None)
    confidence: Optional[float] = Field(default=None)

    text_preview: Optional[str] = Field(default=None)

    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # relationships
    message: "Message" = Relationship(back_populates="prompt_entities")
