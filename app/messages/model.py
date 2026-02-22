from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.common.enums import MessageInputType, MessageRole, RuleAction, ScanStatus


class Message(SQLModel, table=True):
    """
    NOTE:
    - created_at is often enough; updated_at optional for messages.
    - if you want updated_at, inherit TimestampMixin.
    """

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "sequence_number", name="uq_messages_convo_seq"
        ),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_messages_content_hash", "content_hash"),
        Index("ix_messages_final_action", "final_action"),
        Index("ix_messages_scan_status", "scan_status"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    conversation_id: UUID = Field(foreign_key="conversations.id", nullable=False)

    # required
    role: MessageRole = Field(
        sa_column=sa.Column(
            sa.Enum(MessageRole, name="message_role", native_enum=True),
            nullable=False,
        )
    )

    sequence_number: int = Field(nullable=False)

    input_type: MessageInputType = Field(
        default=MessageInputType.user_input,
        sa_column=sa.Column(
            sa.Enum(MessageInputType, name="message_input_type", native_enum=True),
            nullable=False,
            server_default=MessageInputType.user_input.value,
        ),
    )

    # privacy mode: you can set content=None but MUST keep content_hash
    content: Optional[str] = Field(default=None)

    content_hash: Optional[str] = Field(
        default=None, sa_column=sa.Column(sa.String(64), nullable=True)
    )

    content_masked: Optional[str] = Field(default=None)

    scan_status: ScanStatus = Field(
        default=ScanStatus.pending,
        sa_column=sa.Column(
            sa.Enum(ScanStatus, name="scan_status", native_enum=True),
            nullable=False,
            server_default=ScanStatus.pending.value,
        ),
    )

    scan_version: int = Field(
        default=1,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default="1"),
    )

    # optional actions (nullable) -> không set server_default
    pre_rag_action: Optional[RuleAction] = Field(
        default=None,
        sa_column=sa.Column(
            sa.Enum(RuleAction, name="rule_action", native_enum=True),
            nullable=True,
        ),
    )

    final_action: Optional[RuleAction] = Field(
        default=None,
        sa_column=sa.Column(
            sa.Enum(RuleAction, name="rule_action", native_enum=True),
            nullable=True,
        ),
    )

    risk_score: Optional[float] = Field(default=None)

    ambiguous: bool = Field(
        default=False,
        sa_column=sa.Column(
            sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
    )

    matched_rule_ids: Optional[list[str]] = Field(
        default=None,
        sa_column=sa.Column(JSONB, nullable=True),
        description="JSON array of rule IDs (as strings) that were hit",
    )

    entities_json: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=sa.Column(JSONB, nullable=True),
    )

    rag_evidence_json: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=sa.Column(JSONB, nullable=True),
    )

    latency_ms: Optional[int] = Field(default=None)

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=sa.Column(sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # relationships
    conversation: "Conversation" = Relationship(back_populates="messages")
    prompt_entities: list["PromptEntity"] = Relationship(back_populates="message")
