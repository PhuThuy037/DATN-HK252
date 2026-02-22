from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.common.bases import TimestampMixin
from app.common.enums import MemberRole, MemberStatus


class CompanyMember(TimestampMixin, SQLModel, table=True):
    __tablename__ = "company_members"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "company_id", name="uq_company_members_user_company"
        ),
        Index("ix_company_members_company_status", "company_id", "status"),
        Index("ix_company_members_user_status", "user_id", "status"),
        Index("ix_company_members_company_role_status", "company_id", "role", "status"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    user_id: UUID = Field(foreign_key="users.id", nullable=False)
    company_id: UUID = Field(foreign_key="companies.id", nullable=False)

    role: MemberRole = Field(
        default=MemberRole.member,
        sa_column=sa.Column(
            sa.Enum(
                MemberRole,
                name="member_role",  # ✅ DB enum type name
                native_enum=True,
            ),
            nullable=False,
            server_default=MemberRole.member.value,  # ✅ DB default
        ),
    )

    status: MemberStatus = Field(
        default=MemberStatus.active,
        sa_column=sa.Column(
            sa.Enum(
                MemberStatus,
                name="member_status",
                native_enum=True,
            ),
            nullable=False,
            server_default=MemberStatus.active.value,
        ),
    )

    joined_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    removed_at: Optional[datetime] = Field(default=None)

    # relationships
    user: "User" = Relationship(back_populates="company_memberships")
    company: "Company" = Relationship(back_populates="members")
