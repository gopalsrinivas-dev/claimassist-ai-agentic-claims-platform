"""One engine per application lifespan, bounded pooling, explicit units of work."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.exceptions import DatabaseUnavailableError
from app.db.errors import DATABASE_AVAILABILITY_ERRORS
from app.db.telemetry import configure_database_logging, install_query_telemetry


def create_database_engine(settings: Settings) -> Engine:
    configure_database_logging()
    url = make_url(settings.database_url.get_secret_value()).set(drivername="postgresql+psycopg")
    engine = create_engine(
        url,
        echo=False,  # Native echo can expose SQL literals even with hide_parameters.
        hide_parameters=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=5,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000"},
    )
    if settings.sql_echo:
        install_query_telemetry(engine)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    try:
        with factory() as session:
            try:
                yield session
                session.commit()
            except BaseException:
                # Includes cancellation; the outer context always attempts close.
                session.rollback()
                raise
    except DATABASE_AVAILABILITY_ERRORS:
        raise DatabaseUnavailableError from None


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    with transaction(factory) as session:
        yield session


# Function scope finishes commit/rollback before FastAPI sends a successful response.
DatabaseSession = Annotated[Session, Depends(get_session, scope="function")]
