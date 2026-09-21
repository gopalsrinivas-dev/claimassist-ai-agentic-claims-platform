"""Deterministic application settings; never consume a developer's local secrets."""

import os
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine

from app.core.config import Settings
from app.main import create_app

POSTGRES_URL = pytest.StashKey[SecretStr]()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--postgres-integration",
        action="store_true",
        default=False,
        help="Run integration tests against an explicitly configured disposable PostgreSQL DB",
    )


def pytest_configure(config: pytest.Config) -> None:
    # Pytest creates basetemp itself, but requires its parent on a clean checkout.
    (config.rootpath / ".tmp").mkdir(exist_ok=True)
    if config.getoption("--postgres-integration"):
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise pytest.UsageError(
                "PostgreSQL integration tests require DATABASE_URL for a disposable database"
            )
        config.stash[POSTGRES_URL] = SecretStr(url)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--postgres-integration"):
        for item in items:
            if "postgres_integration" in item.keywords:
                item.add_marker(
                    pytest.mark.skip(
                        reason="Use --postgres-integration with a disposable PostgreSQL database"
                    )
                )


@pytest.fixture
def postgres_settings(request: pytest.FixtureRequest) -> Settings:
    return Settings(database_url=request.config.stash[POSTGRES_URL], app_env="test")


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
        monkeypatch.delenv(field.lower(), raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:synthetic@db.test/claimassist_db")


@pytest.fixture
def settings() -> Settings:
    return Settings(app_env="test")


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture(autouse=True)
def database_engine(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> MagicMock:
    """Unit tests never import a driver or connect; integration tests use the real lifespan."""
    engine = MagicMock(spec=Engine)
    engine.connect.return_value.__enter__.return_value.scalar.return_value = 1
    if "postgres_integration" not in request.keywords:
        monkeypatch.setattr("app.core.lifecycle.create_database_engine", lambda settings: engine)
    return engine


@pytest.fixture
def database_connection(database_engine: MagicMock) -> MagicMock:
    connect: MagicMock = database_engine.connect
    return connect


@pytest.fixture
def engine_constructor(monkeypatch: pytest.MonkeyPatch, database_engine: MagicMock) -> MagicMock:
    constructor = MagicMock(return_value=database_engine)
    monkeypatch.setattr("app.db.session.create_engine", constructor)
    return constructor


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
