from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from sqlalchemy.exc import OperationalError

from alembic import command

BACKEND = Path(__file__).resolve().parents[1]
REVISION = "20260921_0001"
IDENTITY_REVISION = "20260921_0002"


def configuration(output: StringIO | None = None) -> Config:
    return Config(str(BACKEND / "alembic.ini"), output_buffer=output)


def test_baseline_remains_empty_and_identity_is_single_head() -> None:
    scripts = ScriptDirectory.from_config(configuration())
    assert scripts.get_heads() == [IDENTITY_REVISION]
    identity = scripts.get_revision(IDENTITY_REVISION)
    assert identity is not None
    assert identity.down_revision == REVISION
    revision = scripts.get_revision(REVISION)
    assert revision is not None
    assert revision.down_revision is None
    assert revision.module.upgrade() is None
    assert revision.module.downgrade() is None


def test_postgres_upgrade_and_downgrade_sql() -> None:
    output = StringIO()
    command.upgrade(configuration(output), REVISION, sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE alembic_version" in sql
    assert f"'{REVISION}'" in sql
    assert sql.count("CREATE TABLE") == 1
    output = StringIO()
    command.downgrade(configuration(output), f"{REVISION}:base", sql=True)
    assert "DELETE FROM alembic_version" in output.getvalue()
    assert "CREATE TABLE" not in output.getvalue()


def test_alembic_online_configures_connection_and_disposes(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = MagicMock()
    configure = MagicMock()
    run = MagicMock()
    monkeypatch.setattr("app.db.session.create_database_engine", lambda settings: engine)
    monkeypatch.setattr("alembic.context.configure", configure)
    monkeypatch.setattr("alembic.context.begin_transaction", MagicMock())
    monkeypatch.setattr("alembic.context.run_migrations", run)
    command.upgrade(configuration(), "head")
    assert (
        configure.call_args.kwargs["connection"]
        is engine.connect.return_value.__enter__.return_value
    )
    run.assert_called_once()
    engine.dispose.assert_called_once()


def test_alembic_failure_hides_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engine = MagicMock()
    engine.connect.side_effect = OperationalError(
        "SYNTHETIC_PRIVATE", {}, RuntimeError("SYNTHETIC_PRIVATE")
    )
    monkeypatch.setattr("app.db.session.create_database_engine", lambda settings: engine)
    with pytest.raises(CommandError) as caught:
        command.upgrade(configuration(), "head")
    assert "SYNTHETIC_PRIVATE" not in str(caught.value) + capsys.readouterr().out
    engine.dispose.assert_called_once()


def test_alembic_invalid_configuration_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "SYNTHETIC_PRIVATE")
    with pytest.raises(CommandError, match="Invalid application database configuration") as caught:
        command.upgrade(configuration(), "head")
    assert "SYNTHETIC_PRIVATE" not in str(caught.value)


def test_identity_migration_sql_contains_only_documented_schema() -> None:
    output = StringIO()
    command.upgrade(configuration(output), f"{REVISION}:head", sql=True)
    sql = output.getvalue()
    assert sql.count("CREATE TABLE") == 3
    for table in ("users", "roles", "user_roles"):
        assert f"CREATE TABLE {table}" in sql
    assert "PRIMARY KEY (user_id, role_id)" in sql
    assert "FOREIGN KEY(user_id) REFERENCES users (id)" in sql
    assert "FOREIGN KEY(role_id) REFERENCES roles (id)" in sql
    assert "CREATE INDEX ix_user_roles_role_id" in sql
    assert "INSERT INTO users" not in sql
    assert "INSERT INTO roles" not in sql
    output = StringIO()
    command.downgrade(configuration(output), f"{IDENTITY_REVISION}:{REVISION}", sql=True)
    sql = output.getvalue()
    assert sql.count("DROP TABLE") == 3
    assert sql.index("DROP TABLE user_roles") < sql.index("DROP TABLE roles")
    assert sql.index("DROP TABLE user_roles") < sql.index("DROP TABLE users")
