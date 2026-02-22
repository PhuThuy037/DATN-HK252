from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel

from app.common.bases import TimestampMixin
from app.common.enums import UserStatus
from datetime import datetime


class User(TimestampMixin, SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, nullable=False, sa_column_kwargs={"unique": True})
    hashed_password: str = Field(nullable=False)
    name: Optional[str] = Field(default=None)
    status: UserStatus = Field(
        default=UserStatus.active,
        sa_column=sa.Column(
            sa.Enum(
                UserStatus,
                name="user_status",
                native_enum=True,
            ),
            nullable=False,
            server_default=UserStatus.active.value,
        ),
    )

    # relationships
    company_memberships: list["CompanyMember"] = Relationship(back_populates="user")
    conversations: list["Conversation"] = Relationship(back_populates="user")
    created_rules: list["Rule"] = Relationship(back_populates="creator")
    refresh_tokens: list["RefreshToken"] = Relationship(back_populates="user")


class RefreshToken(TimestampMixin, SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(
        sa_column=sa.Column(
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    token_hash: str = Field(nullable=False, index=True)

    expires_at: datetime = Field(nullable=False)

    revoked_at: datetime | None = Field(default=None)

    # relationship (optional nhưng nên có)
    user: "User" = Relationship(back_populates="refresh_tokens")