"""Document/evidence persistence against an explicitly disposable PostgreSQL DB."""

from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from pydantic import JsonValue
from sqlalchemy import Engine, MetaData, Table, func, insert, inspect, null, select, text, update
from sqlalchemy.dialects.postgresql.base import PGInspector
from sqlalchemy.exc import DataError, IntegrityError

from alembic import command
from app.db.base import Base
from app.db.session import create_session_factory, transaction
from app.db.telemetry import install_query_telemetry
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
from app.observability.logging import configure_logging

from .test_domain import SYNTHETIC_HASH, claim_graph

pytestmark = pytest.mark.postgres_integration
DOMAIN_REVISION = "20260922_0003"
EVIDENCE_REVISION = "20260924_0004"
EVIDENCE_MODELS = (ClaimDocument, ExtractedFact, PolicyChunk)
PRIVATE = "SYNTHETIC_PRIVATE '); DROP TABLE claims; -- <script>untrusted</script>"


def evidence_graph() -> ClaimDocument:
    claim = claim_graph()
    claim.policy_version.chunks.append(
        PolicyChunk(
            section="Synthetic section",
            clause_id="SYN-1",
            page=2,
            chunk_text=PRIVATE,
            chunk_hash="b" * 64,
        )
    )
    return ClaimDocument(
        claim=claim,
        uploader=claim.creator,
        document_type=DocumentType.HOSPITAL_BILL,
        original_filename="synthetic.pdf",
        object_key="synthetic/document-1",
        sha256="a" * 64,
        content_type="application/pdf",
        size_bytes=2**32,
        facts=[
            ExtractedFact(
                fact_type="synthetic_total",
                value_json={"amount": "123.45", "source": [True, None]},
                normalized_value="123.45",
                source_page=3,
                source_span=PRIVATE,
                extractor_version="synthetic-v1",
                confidence=Decimal("0.9876"),
            )
        ],
    )


def persist_evidence(engine: Engine) -> UUID:
    with transaction(create_session_factory(engine)) as session:
        document = evidence_graph()
        session.add(document)
        session.flush()
        return document.id


def assert_metadata_agreement(engine: Engine) -> None:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_server_default": True})
        assert context.get_current_revision() == EVIDENCE_REVISION
        assert compare_metadata(context, Base.metadata) == []
    enums = {
        enum["name"]: enum["labels"] for enum in cast(PGInspector, inspect(engine)).get_enums()
    }
    assert enums["claim_document_type"] == [item.value for item in DocumentType]
    assert enums["document_processing_status"] == [item.value for item in DocumentProcessingStatus]


def test_evidence_migration_round_trip(domain_engine: Engine, migration_config: Config) -> None:
    assert_metadata_agreement(domain_engine)
    command.heads(migration_config)
    command.current(migration_config, check_heads=True)
    command.check(migration_config)
    document_id = persist_evidence(domain_engine)
    with transaction(create_session_factory(domain_engine)) as session:
        document = session.get(ClaimDocument, document_id)
        assert document is not None
        claim_id, user_id, version_id = (
            document.claim_id,
            document.uploaded_by,
            document.claim.policy_version_id,
        )
    command.downgrade(migration_config, DOMAIN_REVISION)
    assert not {model.__tablename__ for model in EVIDENCE_MODELS} & set(
        inspect(domain_engine).get_table_names()
    )
    assert not {"claim_document_type", "document_processing_status"} & {
        enum["name"] for enum in cast(PGInspector, inspect(domain_engine)).get_enums()
    }
    with domain_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == DOMAIN_REVISION
        assert connection.scalar(select(Claim.id)) == claim_id
        assert connection.scalar(select(User.id)) == user_id
        assert connection.scalar(select(PolicyVersion.id)) == version_id
    command.upgrade(migration_config, "head")
    command.current(migration_config, check_heads=True)
    command.check(migration_config)
    assert_metadata_agreement(domain_engine)
    with transaction(create_session_factory(domain_engine)) as session:
        document = ClaimDocument(
            claim_id=claim_id,
            uploaded_by=user_id,
            document_type=DocumentType.CLAIM_FORM,
            original_filename="synthetic.pdf",
            object_key="synthetic/recreated",
            sha256="c" * 64,
            content_type="application/pdf",
            size_bytes=1,
        )
        session.add(document)
        session.flush()
        assert document.processing_status is DocumentProcessingStatus.UPLOADED


def test_evidence_round_trip_defaults_provenance_and_timestamps(domain_engine: Engine) -> None:
    document_id = persist_evidence(domain_engine)
    factory = create_session_factory(domain_engine)
    with transaction(factory) as session:
        document = session.get(ClaimDocument, document_id)
        assert document is not None
        assert document.claim.documents == [document]
        assert document.uploader is document.claim.creator
        assert document.processing_status is DocumentProcessingStatus.UPLOADED
        assert document.document_type is DocumentType.HOSPITAL_BILL
        assert document.sha256 == "a" * 64 and document.size_bytes == 2**32
        assert document.original_filename == "synthetic.pdf"
        assert document.object_key == "synthetic/document-1"
        assert document.content_type == "application/pdf"
        fact = document.facts[0]
        assert fact.claim_document is document
        assert fact.value_json == {"amount": "123.45", "source": [True, None]}
        assert fact.normalized_value == "123.45"
        assert fact.source_page == 3 and fact.source_span == PRIVATE
        assert fact.extractor_version == "synthetic-v1"
        assert fact.confidence == Decimal("0.9876")
        assert fact.created_at.utcoffset() is not None
        chunk = document.claim.policy_version.chunks[0]
        assert chunk.policy_version is document.claim.policy_version
        assert (chunk.section, chunk.clause_id, chunk.page) == ("Synthetic section", "SYN-1", 2)
        assert chunk.chunk_text == PRIVATE and chunk.chunk_hash == "b" * 64
        assert chunk.metadata_json == {}
        assert document.created_at.utcoffset() is not None
        assert document.updated_at.utcoffset() is not None
        created, updated = document.created_at, document.updated_at
    with transaction(factory) as session:
        document = session.get(ClaimDocument, document_id)
        assert document is not None
        document.processing_status = DocumentProcessingStatus.PROCESSING
    with transaction(factory) as session:
        document = session.get(ClaimDocument, document_id)
        assert document is not None
        assert document.created_at == created and document.updated_at > updated


@pytest.mark.parametrize("value", list(DocumentType) + list(DocumentProcessingStatus))
def test_all_document_enum_values_persist(
    domain_engine: Engine,
    value: DocumentType | DocumentProcessingStatus,
) -> None:
    with transaction(create_session_factory(domain_engine)) as session:
        document = evidence_graph()
        if isinstance(value, DocumentType):
            document.document_type = value
        else:
            document.processing_status = value
        session.add(document)
    with transaction(create_session_factory(domain_engine)) as session:
        document = session.scalars(select(ClaimDocument)).one()
        assert value in (document.document_type, document.processing_status)


@pytest.mark.parametrize(
    "column,value",
    [
        ("document_type", "POLICY_DOCUMENT"),
        ("document_type", "UNKNOWN"),
        ("processing_status", "READY"),
    ],
)
def test_database_rejects_unknown_enum(domain_engine: Engine, column: str, value: str) -> None:
    persist_evidence(domain_engine)
    # Fixed SQL statements bypass ORM enum validation; parameters remain bound.
    statements = {
        "document_type": text("UPDATE claim_documents SET document_type = :value"),
        "processing_status": text("UPDATE claim_documents SET processing_status = :value"),
    }
    with pytest.raises(DataError) as caught, domain_engine.begin() as connection:
        connection.execute(statements[column], {"value": value})
    assert getattr(caught.value.orig, "sqlstate", None) == "22P02"


@pytest.mark.parametrize("model", EVIDENCE_MODELS)
def test_required_fields_reject_sql_null(domain_engine: Engine, model: type) -> None:
    persist_evidence(domain_engine)
    table = cast(Table, inspect(model).local_table)
    for column in table.c:
        if column.nullable:
            continue
        with pytest.raises(IntegrityError) as caught, domain_engine.begin() as connection:
            connection.execute(update(table).values({column.name: null()}))
        assert getattr(caught.value.orig, "sqlstate", None) == "23502", column.name


@pytest.mark.parametrize(
    "model,column",
    [
        (ClaimDocument, "claim_id"),
        (ClaimDocument, "uploaded_by"),
        (ExtractedFact, "claim_document_id"),
        (PolicyChunk, "policy_version_id"),
    ],
)
def test_missing_parent_rejected(domain_engine: Engine, model: type, column: str) -> None:
    persist_evidence(domain_engine)
    with pytest.raises(IntegrityError) as caught, domain_engine.begin() as connection:
        connection.execute(update(model).values({column: uuid4()}))
    assert getattr(caught.value.orig, "sqlstate", None) == "23503"


@pytest.mark.parametrize("duplicate", ["object_key", "claim_hash", "version_hash"])
def test_uniqueness_and_transaction_rollback(domain_engine: Engine, duplicate: str) -> None:
    persist_evidence(domain_engine)
    with (
        pytest.raises(IntegrityError) as caught,
        transaction(create_session_factory(domain_engine)) as session,
    ):
        document = session.scalars(select(ClaimDocument)).one()
        document.original_filename = "must roll back"
        session.flush()
        if duplicate == "version_hash":
            session.add(
                PolicyChunk(
                    policy_version=document.claim.policy_version,
                    chunk_text="Duplicate",
                    chunk_hash="b" * 64,
                )
            )
        else:
            session.add(
                ClaimDocument(
                    claim=document.claim,
                    uploader=document.uploader,
                    document_type=DocumentType.CLAIM_FORM,
                    original_filename="duplicate.pdf",
                    content_type="application/pdf",
                    size_bytes=1,
                    object_key=document.object_key
                    if duplicate == "object_key"
                    else "synthetic/other",
                    sha256=document.sha256 if duplicate == "claim_hash" else "c" * 64,
                )
            )
    assert getattr(caught.value.orig, "sqlstate", None) == "23505"
    with transaction(create_session_factory(domain_engine)) as session:
        assert session.scalars(select(ClaimDocument)).one().original_filename == "synthetic.pdf"
        assert session.scalar(select(func.count()).select_from(ClaimDocument)) == 1
        assert session.scalar(select(func.count()).select_from(PolicyChunk)) == 1


@pytest.mark.parametrize("parent", ["claim", "uploader", "document", "version"])
def test_evidence_prevents_parent_deletion(domain_engine: Engine, parent: str) -> None:
    persist_evidence(domain_engine)
    with (
        pytest.raises(IntegrityError) as caught,
        transaction(create_session_factory(domain_engine)) as session,
    ):
        document = session.scalars(select(ClaimDocument)).one()
        # Isolate each new FK from existing claim-line/claim-creator/version FKs.
        target: Claim | User | PolicyVersion | ClaimDocument
        if parent == "claim":
            for line in document.claim.lines:
                session.delete(line)
            assert document.claim.documents == [document]
            target = document.claim
        elif parent == "uploader":
            uploader = User(
                email="uploader@example.invalid",
                password_hash=SYNTHETIC_HASH,
                display_name="Synthetic uploader",
            )
            document.uploader = uploader
            session.add(uploader)
            session.flush()
            target = uploader
        elif parent == "version":
            version = PolicyVersion(
                policy=document.claim.policy_version.policy,
                version_code="V2",
                effective_from=date(2026, 1, 1),
                document_sha256="c" * 64,
            )
            document.claim.policy_version.chunks[0].policy_version = version
            session.add(version)
            session.flush()
            assert len(version.chunks) == 1
            target = version
        else:
            assert len(document.facts) == 1
            target = document
        session.flush()
        session.delete(target)
    assert getattr(caught.value.orig, "sqlstate", None) == "23503"
    with domain_engine.connect() as connection:
        for model in EVIDENCE_MODELS:
            assert connection.scalar(select(func.count()).select_from(model)) == 1


def test_explicit_evidence_deletion(domain_engine: Engine) -> None:
    persist_evidence(domain_engine)
    with transaction(create_session_factory(domain_engine)) as session:
        fact = session.scalars(select(ExtractedFact)).one()
        session.delete(fact)
        session.flush()
        session.delete(session.scalars(select(ClaimDocument)).one())
        session.delete(session.scalars(select(PolicyChunk)).one())
    with domain_engine.connect() as connection:
        for model in EVIDENCE_MODELS:
            assert connection.scalar(select(func.count()).select_from(model)) == 0
        assert connection.scalar(select(func.count()).select_from(Claim)) == 1


@pytest.mark.parametrize(
    "value", [{"nested": [1, True, None]}, [1, "synthetic"], "synthetic", 12, 1.25, False, None]
)
def test_json_values_and_optional_fields(domain_engine: Engine, value: JsonValue) -> None:
    persist_evidence(domain_engine)
    with transaction(create_session_factory(domain_engine)) as session:
        fact = session.scalars(select(ExtractedFact)).one()
        fact.value_json = value
        fact.normalized_value = fact.source_span = fact.confidence = fact.source_page = None
        chunk = session.scalars(select(PolicyChunk)).one()
        chunk.section = chunk.clause_id = chunk.page = None
        chunk.metadata_json = {"synthetic": value}
    with transaction(create_session_factory(domain_engine)) as session:
        fact = session.scalars(select(ExtractedFact)).one()
        assert fact.value_json == value
        assert all(
            value is None
            for value in (
                fact.normalized_value,
                fact.source_span,
                fact.confidence,
                fact.source_page,
            )
        )
        chunk = session.scalars(select(PolicyChunk)).one()
        assert all(value is None for value in (chunk.section, chunk.clause_id, chunk.page))
        assert chunk.metadata_json == {"synthetic": value}


def test_server_defaults_without_orm(domain_engine: Engine) -> None:
    persist_evidence(domain_engine)
    metadata = MetaData()
    documents = Table("claim_documents", metadata, autoload_with=domain_engine)
    chunks = Table("policy_chunks", metadata, autoload_with=domain_engine)
    with domain_engine.begin() as connection:
        row = (
            connection.execute(
                insert(documents)
                .values(
                    id=uuid4(),
                    claim_id=connection.scalar(select(Claim.id)),
                    uploaded_by=connection.scalar(select(User.id)),
                    document_type="CLAIM_FORM",
                    original_filename="synthetic.pdf",
                    object_key="synthetic/defaults",
                    sha256="d" * 64,
                    content_type="application/pdf",
                    size_bytes=1,
                )
                .returning(documents)
            )
            .mappings()
            .one()
        )
        assert row["processing_status"] == "UPLOADED"
        assert (
            row["created_at"].utcoffset() is not None and row["updated_at"].utcoffset() is not None
        )
        row = (
            connection.execute(
                insert(chunks)
                .values(
                    id=uuid4(),
                    policy_version_id=connection.scalar(select(PolicyVersion.id)),
                    chunk_text="Synthetic",
                    chunk_hash="d" * 64,
                )
                .returning(chunks)
            )
            .mappings()
            .one()
        )
        assert row["metadata"] == {}


def test_composite_keys_are_parent_scoped_and_metadata_defaults_independent(
    domain_engine: Engine,
) -> None:
    persist_evidence(domain_engine)
    with transaction(create_session_factory(domain_engine)) as session:
        first = session.scalars(select(ClaimDocument)).one()
        second_claim = claim_graph()
        second_claim.claim_number = "SYNTHETIC-SECOND"
        second_claim.member = first.claim.member
        second_claim.provider = first.claim.provider
        second_claim.creator = first.uploader
        second_claim.policy_version.policy = first.claim.policy_version.policy
        second_claim.policy_version.version_code = "V2"
        second = ClaimDocument(
            claim=second_claim,
            uploader=first.uploader,
            document_type=first.document_type,
            original_filename="second.pdf",
            object_key="synthetic/second",
            sha256=first.sha256,
            content_type="application/pdf",
            size_bytes=1,
        )
        chunk = PolicyChunk(
            policy_version=second_claim.policy_version, chunk_text="Synthetic", chunk_hash="b" * 64
        )
        session.add_all([second, chunk])
        session.flush()
        first_chunk = first.claim.policy_version.chunks[0]
        assert chunk.metadata_json == first_chunk.metadata_json == {}
        assert chunk.metadata_json is not first_chunk.metadata_json
    with domain_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(ClaimDocument)) == 2
        assert connection.scalar(select(func.count()).select_from(PolicyChunk)) == 2


def test_untrusted_evidence_is_data_and_not_logged(
    domain_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO")
    install_query_telemetry(domain_engine)
    persist_evidence(domain_engine)
    with (
        pytest.raises(IntegrityError),
        transaction(create_session_factory(domain_engine)) as session,
    ):
        document = session.scalars(select(ClaimDocument)).one()
        session.add(
            PolicyChunk(
                policy_version=document.claim.policy_version,
                chunk_text=PRIVATE,
                chunk_hash="b" * 64,
            )
        )
    output = capsys.readouterr()
    assert "database.query.completed" in output.out
    assert PRIVATE not in output.out + output.err
    assert "synthetic/document-1" not in output.out + output.err
