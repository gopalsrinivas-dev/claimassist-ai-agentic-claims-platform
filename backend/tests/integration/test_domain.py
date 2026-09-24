"""PostgreSQL domain integrity, concurrency, and reversible schema verification."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, MetaData, Table, func, insert, inspect, select, text, update
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from alembic import command
from app.db.session import create_session_factory, transaction
from app.db.telemetry import install_query_telemetry
from app.domain.models import (
    Claim,
    ClaimLine,
    ClaimStatus,
    Member,
    Policy,
    PolicyIndexStatus,
    PolicyVersion,
    Provider,
)
from app.identity.models import User
from app.observability.logging import configure_logging

pytestmark = pytest.mark.postgres_integration
IDENTITY_REVISION = "20260921_0002"
DOMAIN_REVISION = "20260922_0003"
DOMAIN_MODELS = (Member, Provider, Policy, PolicyVersion, Claim, ClaimLine)
SYNTHETIC_HASH = "SYNTHETIC_HASH"


def claim_graph() -> Claim:
    """Build only synthetic data; callers add the graph in one unit of work."""
    claim = Claim(
        claim_number="SYNTHETIC-CLAIM",
        member=Member(member_number="SYNTHETIC-MEMBER", display_name="Synthetic member"),
        provider=Provider(provider_code="SYNTHETIC-PROVIDER", name="Synthetic provider"),
        policy_version=PolicyVersion(
            policy=Policy(policy_number="SYNTHETIC-POLICY", name="Synthetic policy"),
            version_code="V1",
            effective_from=date(2026, 1, 1),
            document_sha256="a" * 64,
        ),
        creator=User(
            email="synthetic@example.invalid",
            password_hash=SYNTHETIC_HASH,
            display_name="Synthetic creator",
        ),
        status=ClaimStatus.DRAFT,
        service_start_date=date(2026, 2, 1),
        service_end_date=date(2026, 2, 1),
        claimed_amount=Decimal("123.45"),
        currency="USD",
    )
    claim.lines.append(ClaimLine(line_number=1, amount=Decimal("123.45")))
    return claim


def persist_claim(engine: Engine) -> UUID:
    with transaction(create_session_factory(engine)) as session:
        claim = claim_graph()
        session.add(claim)
        session.flush()
        return claim.id


def test_domain_migration_round_trip(domain_engine: Engine, migration_config: Config) -> None:
    with domain_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == DOMAIN_REVISION
    command.current(migration_config, check_heads=True)
    command.check(migration_config)
    assert set(inspect(domain_engine).get_table_names()) == {
        "alembic_version",
        "users",
        "roles",
        "user_roles",
        "members",
        "providers",
        "policies",
        "policy_versions",
        "claims",
        "claim_lines",
    }
    claim_id = persist_claim(domain_engine)
    with transaction(create_session_factory(domain_engine)) as session:
        claim = session.get(Claim, claim_id)
        assert claim is not None
        creator_id = claim.created_by
    command.downgrade(migration_config, IDENTITY_REVISION)
    assert set(inspect(domain_engine).get_table_names()) == {
        "alembic_version",
        "users",
        "roles",
        "user_roles",
    }
    with domain_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == IDENTITY_REVISION
        assert connection.scalar(select(User.id)) == creator_id
    assert not {"claim_status", "policy_index_status"} & {
        enum["name"] for enum in inspect(domain_engine).get_enums()
    }
    command.upgrade(migration_config, "head")
    command.current(migration_config, check_heads=True)
    command.check(migration_config)
    with transaction(create_session_factory(domain_engine)) as session:
        creator = session.get(User, creator_id)
        assert creator is not None
        session.delete(creator)
    persist_claim(domain_engine)


def test_persisted_graph_and_exact_money(domain_engine: Engine) -> None:
    claim_id = persist_claim(domain_engine)
    with transaction(create_session_factory(domain_engine)) as session:
        claim = session.get(Claim, claim_id)
        assert claim is not None
        assert claim.member.claims == claim.provider.claims == [claim]
        assert claim.policy_version.claims == [claim]
        assert claim.policy_version.policy.versions == [claim.policy_version]
        assert claim.creator.id == claim.created_by
        assert claim.lines[0].claim is claim
        assert claim.claimed_amount == claim.lines[0].amount == Decimal("123.45")
        assert isinstance(claim.claimed_amount, Decimal)
        assert claim.claim_version == claim.row_version == 1
        assert claim.status is ClaimStatus.DRAFT
        assert claim.member.date_of_birth is None
        assert claim.policy_version.effective_to is None
        assert claim.policy_version.index_status is PolicyIndexStatus.PENDING
        assert claim.lines[0].service_date is None
        for instance in (
            claim,
            claim.member,
            claim.provider,
            claim.policy_version,
            claim.policy_version.policy,
        ):
            assert isinstance(instance.id, UUID)
            assert instance.created_at.utcoffset() is not None
            assert instance.updated_at.utcoffset() is not None


@pytest.mark.parametrize(
    "model,column",
    [
        (Member, "member_number"),
        (Provider, "provider_code"),
        (Policy, "policy_number"),
        (PolicyVersion, "version_code"),
        (Claim, "claim_number"),
        (ClaimLine, "line_number"),
    ],
)
def test_domain_unique_constraints(domain_engine: Engine, model: type, column: str) -> None:
    persist_claim(domain_engine)
    with (
        pytest.raises(IntegrityError) as caught,
        transaction(create_session_factory(domain_engine)) as session,
    ):
        existing = session.scalars(select(model)).one()
        values = {field.key: getattr(existing, field.key) for field in inspect(model).columns}
        values["id"] = uuid4()
        assert values[column] is not None
        session.add(model(**values))
    assert getattr(caught.value.orig, "sqlstate", None) == "23505"


@pytest.mark.parametrize(
    "model,column",
    [
        (PolicyVersion, "policy_id"),
        (Claim, "member_id"),
        (Claim, "provider_id"),
        (Claim, "policy_version_id"),
        (Claim, "created_by"),
        (ClaimLine, "claim_id"),
    ],
)
def test_domain_foreign_keys(domain_engine: Engine, model: type, column: str) -> None:
    persist_claim(domain_engine)
    with pytest.raises(IntegrityError) as caught, domain_engine.begin() as connection:
        connection.execute(update(model).values({column: uuid4()}))
    assert getattr(caught.value.orig, "sqlstate", None) == "23503"


@pytest.mark.parametrize("model", (*DOMAIN_MODELS[:-1], User))
def test_referenced_parents_cannot_be_deleted(domain_engine: Engine, model: type) -> None:
    persist_claim(domain_engine)
    with (
        pytest.raises(IntegrityError) as caught,
        transaction(create_session_factory(domain_engine)) as session,
    ):
        target = session.scalars(select(model)).one()
        # Exercise loaded collections as well as the database foreign keys.
        for relationship in inspect(model).relationships:
            getattr(target, relationship.key)
        session.delete(target)
    assert getattr(caught.value.orig, "sqlstate", None) == "23503"


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-0.01")])
def test_claim_amount_must_be_positive_and_failure_rolls_back(
    domain_engine: Engine, amount: Decimal
) -> None:
    with (
        pytest.raises(IntegrityError) as caught,
        transaction(create_session_factory(domain_engine)) as session,
    ):
        claim = claim_graph()
        session.add(claim.member)
        session.flush()
        claim.claimed_amount = amount
        session.add(claim)
    assert getattr(caught.value.orig, "sqlstate", None) == "23514"
    with transaction(create_session_factory(domain_engine)) as session:
        for model in (*DOMAIN_MODELS, User):
            assert session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("target", ["claim", "policy_version"])
def test_invalid_date_ranges(domain_engine: Engine, target: str) -> None:
    claim = claim_graph()
    if target == "claim":
        claim.service_end_date = claim.service_start_date - timedelta(days=1)
    else:
        claim.policy_version.effective_to = claim.policy_version.effective_from - timedelta(days=1)
    with (
        pytest.raises(IntegrityError) as caught,
        transaction(create_session_factory(domain_engine)) as session,
    ):
        session.add(claim)
    assert getattr(caught.value.orig, "sqlstate", None) == "23514"


@pytest.mark.parametrize("status", list(ClaimStatus))
def test_documented_claim_states_persist(domain_engine: Engine, status: ClaimStatus) -> None:
    with transaction(create_session_factory(domain_engine)) as session:
        claim = claim_graph()
        claim.status = status
        session.add(claim)
    with transaction(create_session_factory(domain_engine)) as session:
        assert session.scalars(select(Claim)).one().status is status


def test_unknown_claim_state_rejected_by_database(domain_engine: Engine) -> None:
    persist_claim(domain_engine)
    with pytest.raises(DataError) as caught, domain_engine.begin() as connection:
        connection.execute(text("UPDATE claims SET status = :status"), {"status": "UNDEFINED"})
    assert getattr(caught.value.orig, "sqlstate", None) == "22P02"


def test_stale_claim_write_is_rejected(domain_engine: Engine) -> None:
    claim_id = persist_claim(domain_engine)
    factory = create_session_factory(domain_engine)
    with factory() as first, factory() as second:
        original, stale = first.get(Claim, claim_id), second.get(Claim, claim_id)
        assert original is not None and stale is not None
        created_at, updated_at = original.created_at, original.updated_at
        original.claimed_amount = Decimal("200.01")
        first.commit()
        assert original.row_version == 2
        assert original.claim_version == 1
        stale.claimed_amount = Decimal("300.01")
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()
    with transaction(factory) as session:
        claim = session.get(Claim, claim_id)
        assert claim is not None
        assert claim.claimed_amount == Decimal("200.01")
        assert claim.created_at == created_at
        assert claim.updated_at > updated_at


def test_stale_claim_delete_is_rejected(domain_engine: Engine) -> None:
    claim_id = persist_claim(domain_engine)
    factory = create_session_factory(domain_engine)
    # Remove dependent lines so a foreign key error cannot mask version checking.
    with transaction(factory) as session:
        line = session.scalars(select(ClaimLine)).one()
        session.delete(line)
    with factory() as first, factory() as second:
        original, stale = first.get(Claim, claim_id), second.get(Claim, claim_id)
        assert original is not None and stale is not None
        original.claimed_amount = Decimal("200.01")
        first.commit()
        second.delete(stale)
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()
    with transaction(factory) as session:
        current = session.get(Claim, claim_id)
        assert current is not None
        assert current.row_version == 2
        assert current.claimed_amount == Decimal("200.01")
        session.delete(current)
    with transaction(factory) as session:
        assert session.get(Claim, claim_id) is None
        # Deleting the claim does not delete its referenced entities.
        for model in (Member, Provider, Policy, PolicyVersion, User):
            assert session.scalar(select(func.count()).select_from(model)) == 1


def test_sensitive_domain_values_are_data_and_not_logged(
    domain_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO")
    install_query_telemetry(domain_engine)
    payload = "SYNTHETIC_PRIVATE'); DROP TABLE claims; --"
    with transaction(create_session_factory(domain_engine)) as session:
        claim = claim_graph()
        claim.member.display_name = payload
        claim.lines[0].description = payload
        session.add(claim)
    with transaction(create_session_factory(domain_engine)) as session:
        claim = session.scalars(select(Claim)).one()
        assert claim.member.display_name == claim.lines[0].description == payload
    with (
        pytest.raises(IntegrityError),
        transaction(create_session_factory(domain_engine)) as session,
    ):
        session.add(Member(member_number="SYNTHETIC-MEMBER", display_name=payload))
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "database.query.completed" in output
    assert payload not in output
    assert "SYNTHETIC-MEMBER" not in output


@pytest.mark.parametrize("status", list(PolicyIndexStatus))
def test_documented_policy_index_states_persist(
    domain_engine: Engine, status: PolicyIndexStatus
) -> None:
    with transaction(create_session_factory(domain_engine)) as session:
        claim = claim_graph()
        claim.policy_version.index_status = status
        session.add(claim)
    with transaction(create_session_factory(domain_engine)) as session:
        assert session.scalars(select(PolicyVersion)).one().index_status is status


def test_unknown_policy_index_state_rejected_by_database(domain_engine: Engine) -> None:
    persist_claim(domain_engine)
    with pytest.raises(DataError) as caught, domain_engine.begin() as connection:
        connection.execute(
            text("UPDATE policy_versions SET index_status = :status"), {"status": "UNDEFINED"}
        )
    assert getattr(caught.value.orig, "sqlstate", None) == "22P02"


def test_database_defaults_without_orm(domain_engine: Engine) -> None:
    persist_claim(domain_engine)
    # Reflection omits Python-side defaults, proving PostgreSQL supplies the values.
    metadata = MetaData()
    versions = Table("policy_versions", metadata, autoload_with=domain_engine)
    claims = Table("claims", metadata, autoload_with=domain_engine)
    with domain_engine.begin() as connection:
        policy_id = connection.scalar(select(Policy.id))
        version = (
            connection.execute(
                insert(versions)
                .values(
                    id=uuid4(),
                    policy_id=policy_id,
                    version_code="V2",
                    effective_from=date(2026, 1, 1),
                    effective_to=date(2026, 1, 1),
                    document_sha256="b" * 64,
                )
                .returning(versions)
            )
            .mappings()
            .one()
        )
        assert version["index_status"] == "PENDING"
        assert version["created_at"].utcoffset() is not None
        assert version["updated_at"].utcoffset() is not None
        claim = (
            connection.execute(
                insert(claims)
                .values(
                    id=uuid4(),
                    claim_number="SYNTHETIC-SECOND",
                    member_id=connection.scalar(select(Member.id)),
                    provider_id=connection.scalar(select(Provider.id)),
                    policy_version_id=version["id"],
                    created_by=connection.scalar(select(User.id)),
                    status="DRAFT",
                    service_start_date=date(2026, 1, 1),
                    service_end_date=date(2026, 1, 1),
                    claimed_amount=Decimal("0.01"),
                    currency="USD",
                )
                .returning(claims)
            )
            .mappings()
            .one()
        )
        assert claim["claim_version"] == claim["row_version"] == 1
        assert claim["created_at"].utcoffset() is not None
        assert claim["updated_at"].utcoffset() is not None


@pytest.mark.parametrize("model", DOMAIN_MODELS)
def test_required_domain_fields(domain_engine: Engine, model: type) -> None:
    persist_claim(domain_engine)
    # Each failure gets a fresh transaction, so every required column is exercised.
    for column in inspect(model).columns:
        if column.nullable:
            continue
        with pytest.raises(IntegrityError) as caught, domain_engine.begin() as connection:
            connection.execute(update(model).values({column.key: None}))
        assert getattr(caught.value.orig, "sqlstate", None) == "23502", column.key


@pytest.mark.parametrize("model,column", [(Claim, "claimed_amount"), (ClaimLine, "amount")])
def test_money_precision_overflow_rejected(domain_engine: Engine, model: type, column: str) -> None:
    persist_claim(domain_engine)
    with pytest.raises(DataError) as caught, domain_engine.begin() as connection:
        connection.execute(update(model).values({column: Decimal("1000000000000.00")}))
    assert getattr(caught.value.orig, "sqlstate", None) == "22003"


def test_composite_keys_allow_different_parents(domain_engine: Engine) -> None:
    persist_claim(domain_engine)
    with transaction(create_session_factory(domain_engine)) as session:
        first = session.scalars(select(Claim)).one()
        second = Claim(
            claim_number="SYNTHETIC-SECOND",
            member=first.member,
            provider=first.provider,
            policy_version=PolicyVersion(
                policy=Policy(policy_number="SYNTHETIC-OTHER"),
                version_code="V1",
                effective_from=date(2026, 1, 1),
                document_sha256="b" * 64,
            ),
            creator=first.creator,
            status=ClaimStatus.DRAFT,
            service_start_date=first.service_start_date,
            service_end_date=first.service_end_date,
            claimed_amount=Decimal("1.23"),
            currency="USD",
            lines=[ClaimLine(line_number=1, amount=Decimal("1.23"))],
        )
        session.add(second)
    with transaction(create_session_factory(domain_engine)) as session:
        assert session.scalar(select(func.count()).select_from(ClaimLine)) == 2
        assert session.scalar(select(func.count()).select_from(PolicyVersion)) == 2
