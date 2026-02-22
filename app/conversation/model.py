from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import Index
from sqlmodel import Field, Relationship, SQLModel

from app.common.bases import TimestampMixin
from app.common.enums import ConversationStatus


class Conversation(TimestampMixin, SQLModel, table=True):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_created", "user_id", "created_at"),
        Index("ix_conversations_company_user", "company_id", "user_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(foreign_key="users.id", nullable=False)

    # NULL = user personal chat, NOT NULL = company chat
    company_id: Optional[UUID] = Field(default=None, foreign_key="companies.id")

    title: Optional[str] = Field(default=None)

    status: ConversationStatus = Field(
        default=ConversationStatus.active,
        sa_column=sa.Column(
            sa.Enum(
                ConversationStatus,
                name="conversation_status",
                native_enum=True,
            ),
            nullable=False,
            server_default=ConversationStatus.active.value,
            index=True,
        ),
    )

    model_name: Optional[str] = Field(default=None)
    temperature: Optional[float] = Field(default=None)

    last_sequence_number: int = Field(default=0, nullable=False)

    # relationships
    user: "User" = Relationship(back_populates="conversations")
    company: Optional["Company"] = Relationship(back_populates="conversations")
    messages: list["Message"] = Relationship(back_populates="conversation")
