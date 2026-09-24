"""Canonical evidence mappings and rejection of unsupported enum strings."""

from collections.abc import Callable
from io import StringIO
from typing import Any, cast

import pytest
from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    Enum,
    Numeric,
    Table,
    UniqueConstraint,
    Uuid,
    inspect,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapper
from sqlalchemy.schema import ColumnDefault, DefaultClause
from test_migrations import DOMAIN_REVISION, EVIDENCE_REVISION, configuration

from alembic import command
from app.domain.models import (
    Claim,
    ClaimDocument,
    DocumentProcessingStatus,
    DocumentType,
    ExtractedFact,
    PolicyChunk,
    PolicyVersion,
)
from app.identity.models import User


def test_exact_enum_contracts_and_defaults() -> None:
    assert [item.value for item in DocumentType] == [
        "CLAIM_FORM",
        "HOSPITAL_BILL",
        "DISCHARGE_SUMMARY",
        "PRESCRIPTION",
        "INVESTIGATION_REPORT",
        "IMPLANT_INVOICE",
    ]
    assert [item.value for item in DocumentProcessingStatus] == [
        "UPLOADED",
        "PROCESSING",
        "EXTRACTED",
        "FAILED",
    ]
    document = cast(Table, ClaimDocument.__table__)
    assert document.c.document_type.default is None
    assert document.c.document_type.server_default is None
    default = document.c.processing_status.default
    server_default = document.c.processing_status.server_default
    assert isinstance(default, ColumnDefault)
    assert isinstance(server_default, DefaultClause)
    assert default.arg == DocumentProcessingStatus.UPLOADED
    assert str(server_default.arg) == "'UPLOADED'"
    for name in ("document_type", "processing_status"):
        assert not document.c[name].nullable
        enum_type = document.c[name].type
        assert isinstance(enum_type, Enum)
        # SQLAlchemy's Enum override and PostgreSQL dialect alias are untyped upstream.
        bind_processor = cast(
            Callable[[Dialect], Callable[[str], object]], enum_type.bind_processor
        )
        dialect_factory = cast(Callable[[], Dialect], postgresql.dialect)
        processor = bind_processor(dialect_factory())
        assert processor is not None
        with pytest.raises(LookupError):
            processor("POLICY_DOCUMENT")


def test_evidence_fields_and_types() -> None:
    document = cast(Table, ClaimDocument.__table__)
    fact = cast(Table, ExtractedFact.__table__)
    chunk = cast(Table, PolicyChunk.__table__)
    assert set(document.c.keys()) == {
        "id",
        "claim_id",
        "document_type",
        "original_filename",
        "object_key",
        "sha256",
        "content_type",
        "size_bytes",
        "processing_status",
        "uploaded_by",
        "created_at",
        "updated_at",
    }
    assert set(fact.c.keys()) == {
        "id",
        "claim_document_id",
        "fact_type",
        "value_json",
        "normalized_value",
        "source_page",
        "source_span",
        "extractor_version",
        "confidence",
        "created_at",
    }
    assert set(chunk.c.keys()) == {
        "id",
        "policy_version_id",
        "section",
        "clause_id",
        "page",
        "chunk_text",
        "chunk_hash",
        "metadata",
    }
    assert isinstance(document.c.size_bytes.type, BigInteger)
    assert isinstance(document.c.sha256.type, CHAR)
    assert isinstance(chunk.c.chunk_hash.type, CHAR)
    assert document.c.sha256.type.length == chunk.c.chunk_hash.type.length == 64
    assert isinstance(fact.c.confidence.type, Numeric)
    assert (fact.c.confidence.type.precision, fact.c.confidence.type.scale) == (5, 4)
    assert fact.c.confidence.type.asdecimal
    assert isinstance(fact.c.value_json.type, postgresql.JSONB)
    assert isinstance(chunk.c.metadata.type, postgresql.JSONB)
    assert isinstance(chunk.c.metadata.server_default, DefaultClause)
    assert str(chunk.c.metadata.server_default.arg) == "'{}'::jsonb"
    assert chunk.c.metadata.default is not None
    assert chunk.c.metadata.default.is_callable
    for table, optional in (
        (document, set()),
        (fact, {"normalized_value", "source_page", "source_span", "confidence"}),
        (chunk, {"section", "clause_id", "page"}),
    ):
        assert {c.name for c in table.c if c.nullable} == optional
        assert list(table.primary_key.columns.keys()) == ["id"]
        assert isinstance(table.c.id.type, Uuid)
        assert table.c.id.type.as_uuid
        for column in table.c:
            if isinstance(column.type, DateTime):
                assert column.type.timezone and column.server_default is not None
    assert document.c.updated_at.onupdate is not None
    assert {
        tuple(c.columns.keys()) for c in document.constraints if isinstance(c, UniqueConstraint)
    } == {("object_key",), ("claim_id", "sha256")}
    assert {
        tuple(c.columns.keys()) for c in chunk.constraints if isinstance(c, UniqueConstraint)
    } == {("policy_version_id", "chunk_hash")}


def test_evidence_relationships_and_safe_representations() -> None:
    claim, uploader, version = Claim(), User(), PolicyVersion()
    document = ClaimDocument(claim=claim, uploader=uploader, original_filename="SYNTHETIC_PRIVATE")
    fact = ExtractedFact(claim_document=document, value_json={"private": "SYNTHETIC_PRIVATE"})
    chunk = PolicyChunk(policy_version=version, chunk_text="SYNTHETIC_PRIVATE", metadata_json={})
    assert claim.documents == [document]
    assert document.uploader is uploader
    assert document.facts == [fact]
    assert version.chunks == [chunk]
    assert "SYNTHETIC_PRIVATE" not in repr(document) + repr(fact) + repr(chunk)
    for model, name in ((Claim, "documents"), (ClaimDocument, "facts"), (PolicyVersion, "chunks")):
        relation = cast(Mapper[Any], inspect(model)).relationships[name]
        assert relation.passive_deletes == "all"
        assert not relation.cascade.delete and not relation.cascade.delete_orphan


def test_evidence_migration_sql() -> None:
    output = StringIO()
    command.upgrade(configuration(output), f"{DOMAIN_REVISION}:{EVIDENCE_REVISION}", sql=True)
    sql = output.getvalue()
    assert sql.count("CREATE TABLE") == 3
    assert "POLICY_DOCUMENT" not in sql
    assert "embedding" not in sql.lower()
    assert "DEFAULT 'UPLOADED' NOT NULL" in sql
    assert "UNIQUE (claim_id, sha256)" in sql
    assert "UNIQUE (object_key)" in sql
    assert "UNIQUE (policy_version_id, chunk_hash)" in sql
    assert "value_json JSONB NOT NULL" in sql
    assert "metadata JSONB DEFAULT '{}'::jsonb NOT NULL" in sql
    output = StringIO()
    command.downgrade(configuration(output), f"{EVIDENCE_REVISION}:{DOMAIN_REVISION}", sql=True)
    sql = output.getvalue()
    assert sql.count("DROP TABLE") == 3
    assert sql.index("DROP TABLE extracted_facts") < sql.index("DROP TABLE claim_documents")
    assert "DROP TYPE claim_document_type" in sql
    assert "DROP TYPE document_processing_status" in sql
    assert "DROP TABLE claims" not in sql
