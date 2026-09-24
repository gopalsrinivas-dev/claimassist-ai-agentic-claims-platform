"""Create document/evidence persistence; vector storage is intentionally deferred until the embedding contract is finalized.

Revision ID: 20260924_0004
Revises: 20260922_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260924_0004"
down_revision: str | Sequence[str] | None = "20260922_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "claim_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column(
            "document_type",
            sa.Enum(
                "CLAIM_FORM",
                "HOSPITAL_BILL",
                "DISCHARGE_SUMMARY",
                "PRESCRIPTION",
                "INVESTIGATION_REPORT",
                "IMPLANT_INVOICE",
                name="claim_document_type",
            ),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "processing_status",
            sa.Enum(
                "UPLOADED", "PROCESSING", "EXTRACTED", "FAILED", name="document_processing_status"
            ),
            server_default=sa.text("'UPLOADED'"),
            nullable=False,
        ),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_claim_documents")),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["claims.id"], name=op.f("fk_claim_documents_claim_id_claims")
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], name=op.f("fk_claim_documents_uploaded_by_users")
        ),
        sa.UniqueConstraint("object_key", name=op.f("uq_claim_documents_object_key")),
        sa.UniqueConstraint("claim_id", "sha256", name=op.f("uq_claim_documents_claim_id")),
    )
    op.create_table(
        "extracted_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_document_id", sa.Uuid(), nullable=False),
        sa.Column("fact_type", sa.String(), nullable=False),
        sa.Column("value_json", postgresql.JSONB(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_span", sa.Text(), nullable=True),
        sa.Column("extractor_version", sa.String(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extracted_facts")),
        sa.ForeignKeyConstraint(
            ["claim_document_id"],
            ["claim_documents.id"],
            name=op.f("fk_extracted_facts_claim_document_id_claim_documents"),
        ),
    )
    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("section", sa.String(), nullable=True),
        sa.Column("clause_id", sa.String(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_hash", sa.CHAR(64), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_chunks")),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["policy_versions.id"],
            name=op.f("fk_policy_chunks_policy_version_id_policy_versions"),
        ),
        sa.UniqueConstraint(
            "policy_version_id", "chunk_hash", name=op.f("uq_policy_chunks_policy_version_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("policy_chunks")
    op.drop_table("extracted_facts")
    op.drop_table("claim_documents")
    sa.Enum(name="document_processing_status").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="claim_document_type").drop(op.get_bind(), checkfirst=False)
