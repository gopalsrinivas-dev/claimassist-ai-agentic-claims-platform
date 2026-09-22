"""Opt-in verification against disposable PostgreSQL, never a SQLite substitute."""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, inspect, text
from sqlalchemy.pool import QueuePool

from alembic import command
from app.core.config import Settings
from app.db.health import check_database
from app.db.session import create_database_engine, create_session_factory, transaction
from app.main import create_app

pytestmark = pytest.mark.postgres_integration
BASELINE_REVISION = "20260921_0001"


def test_baseline_upgrade_downgrade_upgrade(
    postgres_engine: Engine,
    postgres_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", postgres_settings.database_url.get_secret_value())
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.upgrade(config, BASELINE_REVISION)
    with postgres_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == BASELINE_REVISION
    command.current(config)
    command.downgrade(config, "base")
    with postgres_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() is None
    command.upgrade(config, BASELINE_REVISION)
    with postgres_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == BASELINE_REVISION
    assert inspect(postgres_engine).get_table_names() == ["alembic_version"]


def test_postgres_commit_rollback_and_cleanup(postgres_engine: Engine) -> None:
    factory = create_session_factory(postgres_engine)
    # Only a connection-local temporary table, never a domain schema object.
    with transaction(factory) as session:
        session.execute(text("CREATE TEMPORARY TABLE transaction_probe (value integer)"))
        session.execute(text("INSERT INTO transaction_probe VALUES (:value)"), {"value": 1})
    try:
        with pytest.raises(ValueError, match="synthetic failure"), transaction(factory) as session:
            session.execute(text("INSERT INTO transaction_probe VALUES (:value)"), {"value": 2})
            raise ValueError("synthetic failure")
        with transaction(factory) as session:
            assert session.scalar(text("SELECT count(*) FROM transaction_probe")) == 1
        assert isinstance(postgres_engine.pool, QueuePool)
        assert postgres_engine.pool.checkedout() == 0
    finally:
        with transaction(factory) as session:
            session.execute(text("DROP TABLE transaction_probe"))


def test_postgres_readiness_and_liveness(postgres_settings: Settings) -> None:
    with TestClient(create_app(postgres_settings)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json() == {"status": "ready"}


def test_postgres_driver_timeouts(postgres_settings: Settings) -> None:
    engine = create_database_engine(postgres_settings)
    received: dict[str, object] = {}

    @event.listens_for(engine, "do_connect")
    def capture(dialect: object, record: object, args: object, kwargs: dict[str, object]) -> None:
        received.update(kwargs)
        raise RuntimeError("connection intercepted")

    try:
        with pytest.raises(RuntimeError, match="connection intercepted"):
            engine.raw_connection()
        assert received["connect_timeout"] == 5
        assert received["options"] == "-c statement_timeout=5000"
    finally:
        engine.dispose()


def test_postgres_query_logging_hides_sql_and_parameters(
    postgres_settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = postgres_settings.model_copy(update={"sql_echo": True})
    from app.observability.logging import configure_logging

    configure_logging("INFO")
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT :value"), {"value": "SYNTHETIC_PRIVATE_PARAMETER"})
            connection.execute(text("SELECT 'SYNTHETIC_PRIVATE_LITERAL'"))
        check_database(engine)
    finally:
        engine.dispose()
    output = capsys.readouterr().out
    assert "database.query.completed" in output
    assert "SYNTHETIC_PRIVATE" not in output
    assert postgres_settings.database_url.get_secret_value() not in output
