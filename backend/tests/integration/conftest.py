"""Explicit disposable PostgreSQL targets; identity tests restore the baseline."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect

from alembic import command
from app.core.config import Settings
from app.db.session import create_database_engine

BASELINE_REVISION = "20260921_0001"


@pytest.fixture
def postgres_engine(postgres_settings: Settings) -> Iterator[Engine]:
    engine = create_database_engine(postgres_settings)
    try:
        assert engine.dialect.name == "postgresql"
        assert set(inspect(engine).get_table_names()) <= {"alembic_version"}, (
            "Integration tests require a disposable database without business tables"
        )
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
            assert current in {None, BASELINE_REVISION}, "Unexpected database migration revision"
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def migration_config(postgres_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", postgres_settings.database_url.get_secret_value())
    return Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))


@pytest.fixture
def identity_engine(postgres_engine: Engine, migration_config: Config) -> Iterator[Engine]:
    # The baseline-only guard must pass before any schema is modified.
    command.upgrade(migration_config, "head")
    try:
        yield postgres_engine
    finally:
        command.downgrade(migration_config, BASELINE_REVISION)
