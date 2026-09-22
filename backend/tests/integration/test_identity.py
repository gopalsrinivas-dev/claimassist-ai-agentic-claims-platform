"""Real PostgreSQL schema, relational integrity, and migration verification."""

from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, func, insert, inspect, select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import selectinload

from alembic import command
from app.db.session import create_session_factory, transaction
from app.db.telemetry import install_query_telemetry
from app.identity.models import Role, User, UserRole
from app.observability.logging import configure_logging

pytestmark = pytest.mark.postgres_integration
BASELINE_REVISION = "20260921_0001"
IDENTITY_REVISION = "20260921_0002"
SYNTHETIC_HASH = "SYNTHETIC_PRIVATE_HASH"


def create_assignment(engine: Engine) -> tuple[UUID, UUID]:
    with transaction(create_session_factory(engine)) as session:
        user = User(
            email="synthetic@example.invalid", password_hash=SYNTHETIC_HASH, display_name="Test"
        )
        role = Role(code="SYNTHETIC_ROLE", name="Synthetic role")
        session.add(UserRole(user=user, role=role))
        session.flush()
        return user.id, role.id


def test_identity_migration_round_trip(identity_engine: Engine, migration_config: Config) -> None:
    assert ScriptDirectory.from_config(migration_config).get_current_head() == IDENTITY_REVISION
    command.current(migration_config, check_heads=True)
    command.check(migration_config)
    assert set(inspect(identity_engine).get_table_names()) == {
        "alembic_version",
        "users",
        "roles",
        "user_roles",
    }
    with identity_engine.connect() as connection:
        for model in (User, Role, UserRole):
            assert connection.scalar(select(func.count()).select_from(model)) == 0
    command.downgrade(migration_config, BASELINE_REVISION)
    assert inspect(identity_engine).get_table_names() == ["alembic_version"]
    with identity_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == BASELINE_REVISION
    command.upgrade(migration_config, "head")
    command.current(migration_config, check_heads=True)
    command.check(migration_config)
    # A write after recreation verifies that the regenerated schema is usable.
    create_assignment(identity_engine)


def test_persisted_relationships_defaults_and_timestamps(identity_engine: Engine) -> None:
    user_id, role_id = create_assignment(identity_engine)
    assert isinstance(user_id, UUID) and isinstance(role_id, UUID)
    factory = create_session_factory(identity_engine)
    with transaction(factory) as session:
        user = session.scalars(select(User).options(selectinload(User.user_roles))).one()
        assert user.id == user_id
        assert user.is_active is True
        # PostgreSQL stores timestamptz instants in UTC; rendering uses session timezone.
        assert user.created_at.utcoffset() is not None
        assert user.updated_at.utcoffset() is not None
        created_at, updated_at = user.created_at, user.updated_at
        assignment = user.user_roles[0]
        assert assignment.role.id == role_id
        assert assignment.role.user_roles == [assignment]
    with transaction(factory) as session:
        user = session.get(User, user_id)
        assert user is not None
        user.display_name = "Updated synthetic user"
    with transaction(factory) as session:
        user = session.get(User, user_id)
        assert user is not None
        assert user.created_at == created_at
        assert user.updated_at > updated_at


@pytest.mark.parametrize("duplicate", ["email", "role_code", "assignment"])
def test_unique_constraints(identity_engine: Engine, duplicate: str) -> None:
    user_id, role_id = create_assignment(identity_engine)
    with (
        pytest.raises(IntegrityError) as caught,
        transaction(create_session_factory(identity_engine)) as session,
    ):
        if duplicate == "email":
            session.add(
                User(
                    email="synthetic@example.invalid",
                    password_hash=SYNTHETIC_HASH,
                    display_name="Other",
                )
            )
        elif duplicate == "role_code":
            session.add(Role(code="SYNTHETIC_ROLE", name="Other"))
        else:
            session.add(UserRole(user_id=user_id, role_id=role_id))
    assert getattr(caught.value.orig, "sqlstate", None) == "23505"
    with transaction(create_session_factory(identity_engine)) as session:
        assert session.scalar(select(func.count()).select_from(UserRole)) == 1


@pytest.mark.parametrize("missing", ["user", "role"])
def test_assignment_foreign_keys(identity_engine: Engine, missing: str) -> None:
    user_id, role_id = create_assignment(identity_engine)
    with (
        pytest.raises(IntegrityError) as caught,
        transaction(create_session_factory(identity_engine)) as session,
    ):
        session.add(
            UserRole(
                user_id=uuid4() if missing == "user" else user_id,
                role_id=uuid4() if missing == "role" else role_id,
            )
        )
    assert getattr(caught.value.orig, "sqlstate", None) == "23503"


@pytest.mark.parametrize("entity", ["user", "role"])
def test_referenced_identity_deletion_is_rejected(identity_engine: Engine, entity: str) -> None:
    user_id, role_id = create_assignment(identity_engine)
    factory = create_session_factory(identity_engine)
    with pytest.raises(IntegrityError) as caught, transaction(factory) as session:
        target = session.get(User, user_id) if entity == "user" else session.get(Role, role_id)
        assert target is not None
        assert len(target.user_roles) == 1
        session.delete(target)
    assert getattr(caught.value.orig, "sqlstate", None) == "23503"
    with transaction(factory) as session:
        assignment = session.get(UserRole, (user_id, role_id))
        assert assignment is not None
        session.delete(assignment)
        session.flush()
        user, role = session.get(User, user_id), session.get(Role, role_id)
        assert user is not None and role is not None
        session.delete(user)
        session.delete(role)


@pytest.mark.parametrize(
    "column",
    ["id", "email", "password_hash", "display_name", "is_active", "created_at", "updated_at"],
)
def test_required_user_fields(identity_engine: Engine, column: str) -> None:
    values: dict[str, object] = {
        "id": uuid4(),
        "email": "synthetic@example.invalid",
        "password_hash": "SYNTHETIC_HASH",
        "display_name": "Synthetic user",
        column: None,
    }
    with pytest.raises(IntegrityError) as caught, identity_engine.begin() as connection:
        connection.execute(insert(User.__table__).values(values))
    assert getattr(caught.value.orig, "sqlstate", None) == "23502"


def test_sql_payload_is_data_and_hash_is_not_logged(
    identity_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO")
    install_query_telemetry(identity_engine)
    payload = "synthetic'); DROP TABLE users; --"
    with transaction(create_session_factory(identity_engine)) as session:
        session.add(
            User(
                email="payload@example.invalid",
                password_hash=SYNTHETIC_HASH,
                display_name=payload,
            )
        )
    with transaction(create_session_factory(identity_engine)) as session:
        assert session.scalars(select(User)).one().display_name == payload
    with (
        pytest.raises(IntegrityError) as caught,
        transaction(create_session_factory(identity_engine)) as session,
    ):
        session.add(
            User(
                email="payload@example.invalid",
                password_hash=SYNTHETIC_HASH,
                display_name=payload,
            )
        )
    assert SYNTHETIC_HASH not in str(caught.value)
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "database.query.completed" in output
    assert "SYNTHETIC_PRIVATE_HASH" not in output
    assert payload not in output


def test_failed_assignment_rolls_back_flushed_user(identity_engine: Engine) -> None:
    factory = create_session_factory(identity_engine)
    with pytest.raises(IntegrityError) as caught, transaction(factory) as session:
        user = User(
            email="rollback@example.invalid",
            password_hash=SYNTHETIC_HASH,
            display_name="Synthetic user",
        )
        session.add(user)
        session.flush()
        session.add(UserRole(user_id=user.id, role_id=uuid4()))
    assert getattr(caught.value.orig, "sqlstate", None) == "23503"
    with transaction(factory) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0
        assert session.scalar(select(func.count()).select_from(UserRole)) == 0


@pytest.mark.parametrize("column", ["user_id", "role_id"])
def test_required_assignment_fields(identity_engine: Engine, column: str) -> None:
    user_id, role_id = create_assignment(identity_engine)
    values: dict[str, object] = {"user_id": user_id, "role_id": role_id, column: None}
    with pytest.raises(IntegrityError) as caught, identity_engine.begin() as connection:
        connection.execute(insert(UserRole.__table__).values(values))
    assert getattr(caught.value.orig, "sqlstate", None) == "23502"


def test_many_to_many_assignments(identity_engine: Engine) -> None:
    factory = create_session_factory(identity_engine)
    with transaction(factory) as session:
        users = [
            User(
                email=f"synthetic{number}@example.invalid",
                password_hash=SYNTHETIC_HASH,
                display_name="Test",
            )
            for number in range(2)
        ]
        roles = [Role(code=f"SYNTHETIC_{number}", name="Test") for number in range(2)]
        for user in users:
            for role in roles:
                session.add(UserRole(user=user, role=role))
    with transaction(factory) as session:
        for user in session.scalars(select(User)):
            assert len(user.user_roles) == 2
        for role in session.scalars(select(Role)):
            assert len(role.user_roles) == 2


@pytest.mark.parametrize("column", ["id", "code", "name"])
def test_required_role_fields(identity_engine: Engine, column: str) -> None:
    values: dict[str, object] = {"id": uuid4(), "code": "SYNTHETIC", "name": "Test", column: None}
    with pytest.raises(IntegrityError) as caught, identity_engine.begin() as connection:
        connection.execute(insert(Role.__table__).values(values))
    assert getattr(caught.value.orig, "sqlstate", None) == "23502"


@pytest.mark.parametrize(
    "column,limit", [("email", 320), ("display_name", 200), ("code", 64), ("name", 120)]
)
def test_identity_field_lengths(identity_engine: Engine, column: str, limit: int) -> None:
    if column in {"email", "display_name"}:
        table = User.__table__
        values: dict[str, object] = {
            "id": uuid4(),
            "email": "synthetic@example.invalid",
            "password_hash": SYNTHETIC_HASH,
            "display_name": "Test",
            column: "x" * (limit + 1),
        }
    else:
        table = Role.__table__
        values = {"id": uuid4(), "code": "SYNTHETIC", "name": "Test", column: "x" * (limit + 1)}
    with pytest.raises(DataError) as caught, identity_engine.begin() as connection:
        connection.execute(insert(table).values(values))
    assert getattr(caught.value.orig, "sqlstate", None) == "22001"
