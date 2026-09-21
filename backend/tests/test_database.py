import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import Engine, event
from sqlalchemy.exc import OperationalError, ProgrammingError, TimeoutError
from sqlalchemy.orm import Session

from app.core.config import BACKEND_ROOT, Settings
from app.core.exceptions import DatabaseUnavailableError
from app.db.base import Base
from app.db.health import check_database
from app.db.session import (
    DatabaseSession,
    create_database_engine,
    create_session_factory,
    transaction,
)
from app.main import create_app
from app.observability.logging import configure_logging

PRIVATE = "SYNTHETIC_PRIVATE"
DECLARED_ENV_FILE = Settings.model_config["env_file"]


def database_failure() -> OperationalError:
    return OperationalError("SELECT " + PRIVATE, {"member": PRIVATE}, RuntimeError(PRIVATE))


def test_database_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql://test:SYNTHETIC_PRIVATE@db.test/claimassist_db"
    monkeypatch.setenv("DATABASE_URL", url)
    settings = Settings()
    assert settings.database_url.get_secret_value() == url
    assert settings.sql_echo is False
    assert PRIVATE not in repr(settings)
    assert PRIVATE not in settings.model_dump_json()
    monkeypatch.setenv("SQL_ECHO", "true")
    assert Settings().sql_echo is True


def test_backend_dotenv_resolution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert Path(__file__).resolve().parents[1] == BACKEND_ROOT
    assert DECLARED_ENV_FILE == BACKEND_ROOT / ".env"
    monkeypatch.delenv("DATABASE_URL")
    dotenv = tmp_path / ".env"
    url = "postgresql+psycopg://test:synthetic@db.test/from_dotenv"
    dotenv.write_text("DATABASE_URL=" + url, encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", dotenv)
    assert Settings().database_url.get_secret_value() == url
    monkeypatch.setenv("DATABASE_URL", url.replace("from_dotenv", "from_environment"))
    assert Settings().database_url.get_secret_value().endswith("/from_environment")


@pytest.mark.parametrize(
    "url",
    [
        "",
        "SYNTHETIC_PRIVATE",
        "sqlite:///SYNTHETIC_PRIVATE",
        "mysql://test:SYNTHETIC_PRIVATE@db.test/db",
        "postgresql+psycopg2://test:SYNTHETIC_PRIVATE@db.test/db",
        "postgresql://test:SYNTHETIC_PRIVATE@/db",
        "postgresql://test:SYNTHETIC_PRIVATE@db.test/",
        "postgresql://test:SYNTHETIC_PRIVATE@db.test:invalid/db",
        "postgresql://test:SYNTHETIC_PRIVATE@db.test:99999/db",
        "postgresql://test:SYNTHETIC_PRIVATE@db.test:0/db",
        "postgresql://test:SYNTHETIC_PRIVATE@db.test/db\n",
    ],
)
def test_invalid_database_settings_are_safe(url: str) -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(database_url=SecretStr(url))
    assert PRIVATE not in str(caught.value)
    assert PRIVATE not in caught.value.json()
    assert PRIVATE not in repr(caught.value.errors())


def test_missing_database_configuration_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:SYNTHETIC_PRIVATE@db.test/db")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEBUG", "true")
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert PRIVATE not in caught.value.json()


def test_invalid_sql_echo_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SQL_ECHO", PRIVATE)
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert PRIVATE not in caught.value.json()


def test_engine_and_session_factory(settings: Settings, engine_constructor: MagicMock) -> None:
    engine = create_database_engine(settings)
    try:
        assert engine_constructor.call_args.args[0].drivername == "postgresql+psycopg"
        assert engine_constructor.call_args.kwargs["echo"] is False
        assert engine_constructor.call_args.kwargs["hide_parameters"] is True
        factory = create_session_factory(engine)
        with factory() as session:
            assert session.bind is engine
            assert session.autoflush is False
            assert session.expire_on_commit is False
        assert not Base.metadata.tables
    finally:
        engine.dispose()


def test_raw_environment_url_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:SYNTHETIC_PRIVATE@db.test:bad/db")
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert PRIVATE not in str(caught.value)
    assert PRIVATE not in caught.value.json()
    assert PRIVATE not in repr(caught.value.errors())


def test_connection_timeouts_cannot_be_overridden_by_url(
    monkeypatch: pytest.MonkeyPatch,
    engine_constructor: MagicMock,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:synthetic@db.test/db?connect_timeout=0")
    engine = create_database_engine(Settings())
    try:
        received = engine_constructor.call_args.kwargs["connect_args"]
        assert received["connect_timeout"] == 5
        assert received["options"] == "-c statement_timeout=5000"
    finally:
        engine.dispose()


def test_session_commits_and_closes() -> None:
    factory = MagicMock()
    session = factory.return_value
    session.__enter__.return_value = session
    with transaction(factory) as actual:
        assert id(actual) == id(session)
    session.commit.assert_called_once()
    session.rollback.assert_not_called()
    session.__exit__.assert_called_once()


@pytest.mark.parametrize("failure_at", ["body", "commit", "rollback", "close", "factory"])
def test_database_failures_cleanup_and_translate(failure_at: str) -> None:
    factory = MagicMock()
    session = factory.return_value
    session.__enter__.return_value = session
    failure = database_failure()
    if failure_at == "factory":
        factory.side_effect = failure
    elif failure_at == "close":
        session.__exit__.side_effect = failure
    elif failure_at in {"commit", "rollback"}:
        getattr(session, failure_at).side_effect = failure
    with pytest.raises(DatabaseUnavailableError) as caught, transaction(factory):
        if failure_at in {"body", "rollback"}:
            raise failure
    assert PRIVATE not in str(caught.value)
    if failure_at != "factory":
        session.__exit__.assert_called_once()
    if failure_at in {"body", "commit", "rollback"}:
        session.rollback.assert_called_once()


def test_non_database_failure_is_rolled_back_and_propagated() -> None:
    factory = MagicMock()
    session = factory.return_value
    session.__enter__.return_value = session
    with pytest.raises(ValueError, match="application failure"), transaction(factory):
        raise ValueError("application failure")
    session.commit.assert_not_called()
    session.rollback.assert_called_once()
    session.__exit__.assert_called_once()


def test_real_session_is_closed_after_commit_or_rollback(
    settings: Settings,
    engine_constructor: MagicMock,
) -> None:
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    sessions: list[Session] = []
    original = Session.close

    def close(session: Session) -> None:
        sessions.append(session)
        original(session)

    from unittest.mock import patch

    try:
        with patch.object(Session, "close", close):
            with transaction(factory) as success:
                success.begin()
            with pytest.raises(ValueError), transaction(factory) as failure:
                failure.begin()
                raise ValueError("test")
        assert sessions == [success, failure]
        assert not success.in_transaction()
        assert not failure.in_transaction()
    finally:
        engine.dispose()


def test_readiness_success_and_connection_release(
    database_connection: MagicMock,
    database_engine: MagicMock,
) -> None:
    engine = database_engine
    try:
        check_database(engine)
        database_connection.return_value.__exit__.assert_called_once()
    finally:
        engine.dispose()


@pytest.mark.parametrize("failure_at", ["connect", "query", "result", "close"])
def test_database_readiness_failure(
    app: FastAPI,
    database_connection: MagicMock,
    failure_at: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    connection = database_connection.return_value.__enter__.return_value
    if failure_at == "connect":
        database_connection.side_effect = database_failure()
    elif failure_at == "query":
        connection.scalar.side_effect = database_failure()
    elif failure_at == "result":
        connection.scalar.return_value = None
    else:
        database_connection.return_value.__exit__.side_effect = database_failure()
    with TestClient(app) as client:
        response = client.get("/ready")
        assert client.get("/health").status_code == 200
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["error"]["correlation_id"] == response.headers["X-Correlation-ID"]
    output = capsys.readouterr().out
    assert PRIVATE not in output + response.text
    failures = [json.loads(line) for line in output.splitlines() if '"request.error"' in line]
    assert len(failures) == 1
    assert failures[0]["dependency"] == "database"
    assert failures[0]["correlation_id"] == response.headers["X-Correlation-ID"]


def test_commit_failure_precedes_success_response(app: FastAPI) -> None:
    @app.get("/test-transaction")
    def endpoint(session: DatabaseSession) -> dict[str, str]:
        return {"status": "success"}

    with TestClient(app) as client:
        factory = MagicMock()
        session = factory.return_value
        session.__enter__.return_value = session
        session.commit.side_effect = database_failure()
        app.state.session_factory = factory
        response = client.get("/test-transaction")
    assert response.status_code == 503
    assert PRIVATE not in response.text
    session.rollback.assert_called_once()
    session.__exit__.assert_called_once()


def test_raw_sqlalchemy_error_has_safe_central_mapping(app: FastAPI) -> None:
    @app.get("/test-db-error")
    def endpoint() -> None:
        raise database_failure()

    with TestClient(app) as client:
        response = client.get("/test-db-error")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert PRIVATE not in response.text


@pytest.mark.parametrize("availability_failure", [True, False])
def test_database_error_classification(
    availability_failure: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(Settings())

    @app.get("/test-db-classification")
    def endpoint(session: DatabaseSession) -> None:
        if availability_failure:
            raise TimeoutError(PRIVATE)
        raise ProgrammingError(PRIVATE, {"private": PRIVATE}, RuntimeError(PRIVATE))

    with TestClient(app) as client:
        response = client.get("/test-db-classification")
    assert response.status_code == (503 if availability_failure else 500)
    assert response.json()["error"]["code"] == (
        "DATABASE_UNAVAILABLE" if availability_failure else "INTERNAL_ERROR"
    )
    output = capsys.readouterr().out
    assert PRIVATE not in output + response.text
    errors = [json.loads(line) for line in output.splitlines() if '"request.error"' in line]
    assert len(errors) == 1
    assert errors[0]["dependency"] == "database"
    assert ("exception_frames" in errors[0]) is not availability_failure


def test_engine_disposed_at_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = MagicMock(spec=Engine)
    monkeypatch.setattr("app.core.lifecycle.create_database_engine", lambda settings: engine)
    with TestClient(create_app(Settings())):
        engine.dispose.assert_not_called()
    engine.dispose.assert_called_once()


def test_sql_echo_uses_safe_telemetry(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    engine_constructor: MagicMock,
) -> None:
    configure_logging("INFO")
    callbacks: dict[str, object] = {}
    monkeypatch.setattr(
        event, "listen", lambda engine, name, handler: callbacks.update({name: handler})
    )
    engine = create_database_engine(Settings(sql_echo=True))
    assert engine_constructor.call_args.kwargs["echo"] is False
    conn = MagicMock()
    conn.info = {}
    before = callbacks["before_cursor_execute"]
    after = callbacks["after_cursor_execute"]
    failed = callbacks["handle_error"]
    assert callable(before) and callable(after) and callable(failed)
    before(conn, None, PRIVATE, {"member": PRIVATE}, None, False)
    after(conn, None, PRIVATE, {"member": PRIVATE}, None, False)
    failed(MagicMock(connection=conn))
    failed(MagicMock(connection=None))
    output = capsys.readouterr().out
    assert PRIVATE not in output
    assert "database.query.completed" in output
    engine.dispose()
