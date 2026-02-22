from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel

from app.common.bases import TimestampMixin
from app.common.enums import CompanyStatus


class Company(TimestampMixin, SQLModel, table=True):
    __tablename__ = "companies"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    name: str = Field(nullable=False, index=True)

    status: CompanyStatus = Field(
        default=CompanyStatus.active,
        sa_column=sa.Column(
            sa.Enum(
                CompanyStatus,
                name="company_status",
                native_enum=True,
            ),
            nullable=False,
            server_default=CompanyStatus.active.value,
            index=True,
        ),
    )

    # relationships
    members: list["CompanyMember"] = Relationship(back_populates="company")
    rules: list["Rule"] = Relationship(back_populates="company")
    conversations: list["Conversation"] = Relationship(back_populates="company")
