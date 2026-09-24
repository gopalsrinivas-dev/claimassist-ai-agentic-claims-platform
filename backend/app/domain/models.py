"""Healthcare claims schema using exact money, business dates, and explicit references."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.identity.models import User


class ClaimStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PROCESSING = "PROCESSING"
    NEED_INFO = "NEED_INFO"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class PolicyIndexStatus(StrEnum):
    PENDING = "PENDING"
    INDEXING = "INDEXING"
    READY = "READY"
    FAILED = "FAILED"


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Member(Timestamps, Base):
    __tablename__ = "members"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    member_number: Mapped[str] = mapped_column(String, unique=True)
    display_name: Mapped[str | None] = mapped_column(String)
    date_of_birth: Mapped[date | None] = mapped_column(Date)

    claims: Mapped[list[Claim]] = relationship(back_populates="member", passive_deletes="all")


class Provider(Timestamps, Base):
    __tablename__ = "providers"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider_code: Mapped[str | None] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)

    claims: Mapped[list[Claim]] = relationship(back_populates="provider", passive_deletes="all")


class Policy(Timestamps, Base):
    __tablename__ = "policies"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    policy_number: Mapped[str | None] = mapped_column(String, unique=True)
    name: Mapped[str | None] = mapped_column(String)

    versions: Mapped[list[PolicyVersion]] = relationship(
        back_populates="policy", passive_deletes="all"
    )


class PolicyVersion(Timestamps, Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_id", "version_code"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="valid_effective_range"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    policy_id: Mapped[UUID] = mapped_column(ForeignKey("policies.id"))
    version_code: Mapped[str] = mapped_column(String)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    document_sha256: Mapped[str] = mapped_column(CHAR(64))
    index_status: Mapped[PolicyIndexStatus] = mapped_column(
        Enum(PolicyIndexStatus, name="policy_index_status", validate_strings=True),
        default=PolicyIndexStatus.PENDING,
        server_default=text("'PENDING'"),
        nullable=False,
    )

    policy: Mapped[Policy] = relationship(back_populates="versions")
    claims: Mapped[list[Claim]] = relationship(
        back_populates="policy_version", passive_deletes="all"
    )


class Claim(Timestamps, Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint("claimed_amount > 0", name="positive_claimed_amount"),
        CheckConstraint("service_end_date >= service_start_date", name="valid_service_range"),
        Index("ix_claims_status_created_at", "status", "created_at"),
        Index("ix_claims_member_id_service_start_date", "member_id", "service_start_date"),
        Index("ix_claims_provider_id_service_start_date", "provider_id", "service_start_date"),
        Index("ix_claims_policy_version_id", "policy_version_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    claim_number: Mapped[str] = mapped_column(String, unique=True)
    member_id: Mapped[UUID] = mapped_column(ForeignKey("members.id"))
    provider_id: Mapped[UUID] = mapped_column(ForeignKey("providers.id"))
    policy_version_id: Mapped[UUID] = mapped_column(ForeignKey("policy_versions.id"))
    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, name="claim_status", validate_strings=True)
    )
    service_start_date: Mapped[date] = mapped_column(Date)
    service_end_date: Mapped[date] = mapped_column(Date)
    claimed_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(CHAR(3))
    claim_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    row_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # ORM flushes reject stale updates/deletes. Bulk SQL must check versions explicitly.
    __mapper_args__ = {"version_id_col": row_version}

    member: Mapped[Member] = relationship(back_populates="claims")
    provider: Mapped[Provider] = relationship(back_populates="claims")
    policy_version: Mapped[PolicyVersion] = relationship(back_populates="claims")
    creator: Mapped[User] = relationship()
    lines: Mapped[list[ClaimLine]] = relationship(back_populates="claim", passive_deletes="all")


class ClaimLine(Base):
    __tablename__ = "claim_lines"
    __table_args__ = (UniqueConstraint("claim_id", "line_number"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("claims.id"))
    line_number: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    service_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    procedure_code: Mapped[str | None] = mapped_column(String)

    claim: Mapped[Claim] = relationship(back_populates="lines")
