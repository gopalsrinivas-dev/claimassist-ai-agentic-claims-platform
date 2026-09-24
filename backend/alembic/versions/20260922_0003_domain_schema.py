"""Create the six core domain tables, constraints, indexes, and status types.

Revision ID: 20260922_0003
Revises: 20260921_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260922_0003"
down_revision: str | Sequence[str] | None = "20260921_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("member_number", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_members")),
        sa.UniqueConstraint("member_number", name=op.f("uq_members_member_number")),
    )
    op.create_table(
        "policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_number", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policies")),
        sa.UniqueConstraint("policy_number", name=op.f("uq_policies_policy_number")),
    )
    op.create_table(
        "providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_code", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_providers")),
        sa.UniqueConstraint("provider_code", name=op.f("uq_providers_provider_code")),
    )
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("version_code", sa.String(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("document_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "index_status",
            sa.Enum("PENDING", "INDEXING", "READY", "FAILED", name="policy_index_status"),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_policy_versions_valid_effective_range"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"], ["policies.id"], name=op.f("fk_policy_versions_policy_id_policies")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_versions")),
        sa.UniqueConstraint("policy_id", "version_code", name=op.f("uq_policy_versions_policy_id")),
    )
    op.create_table(
        "claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_number", sa.String(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "SUBMITTED",
                "PROCESSING",
                "NEED_INFO",
                "READY_FOR_REVIEW",
                "APPROVED",
                "REJECTED",
                "ESCALATED",
                name="claim_status",
            ),
            nullable=False,
        ),
        sa.Column("service_start_date", sa.Date(), nullable=False),
        sa.Column("service_end_date", sa.Date(), nullable=False),
        sa.Column("claimed_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("claim_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("claimed_amount > 0", name=op.f("ck_claims_positive_claimed_amount")),
        sa.CheckConstraint(
            "service_end_date >= service_start_date", name=op.f("ck_claims_valid_service_range")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_claims_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["member_id"], ["members.id"], name=op.f("fk_claims_member_id_members")
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["policy_versions.id"],
            name=op.f("fk_claims_policy_version_id_policy_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["providers.id"], name=op.f("fk_claims_provider_id_providers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_claims")),
        sa.UniqueConstraint("claim_number", name=op.f("uq_claims_claim_number")),
    )
    op.create_index(
        "ix_claims_member_id_service_start_date",
        "claims",
        ["member_id", "service_start_date"],
        unique=False,
    )
    op.create_index("ix_claims_policy_version_id", "claims", ["policy_version_id"], unique=False)
    op.create_index(
        "ix_claims_provider_id_service_start_date",
        "claims",
        ["provider_id", "service_start_date"],
        unique=False,
    )
    op.create_index("ix_claims_status_created_at", "claims", ["status", "created_at"], unique=False)
    op.create_table(
        "claim_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("service_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("procedure_code", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["claims.id"], name=op.f("fk_claim_lines_claim_id_claims")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_claim_lines")),
        sa.UniqueConstraint("claim_id", "line_number", name=op.f("uq_claim_lines_claim_id")),
    )


def downgrade() -> None:
    op.drop_table("claim_lines")
    op.drop_index("ix_claims_status_created_at", table_name="claims")
    op.drop_index("ix_claims_provider_id_service_start_date", table_name="claims")
    op.drop_index("ix_claims_policy_version_id", table_name="claims")
    op.drop_index("ix_claims_member_id_service_start_date", table_name="claims")
    op.drop_table("claims")
    op.drop_table("policy_versions")
    op.drop_table("providers")
    op.drop_table("policies")
    op.drop_table("members")
    # PostgreSQL enums outlive their tables unless explicitly removed.
    sa.Enum(name="claim_status").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="policy_index_status").drop(op.get_bind(), checkfirst=False)
