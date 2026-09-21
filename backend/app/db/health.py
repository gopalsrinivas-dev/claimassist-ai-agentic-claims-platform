"""Connectivity-only readiness: a bounded, read-only query with no automatic retry."""

import logging
from time import perf_counter

from sqlalchemy import Engine, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import DatabaseUnavailableError

logger = logging.getLogger("claimassist.database")


def check_database(engine: Engine) -> None:
    started = perf_counter()
    try:
        with engine.connect() as connection:
            if connection.scalar(select(1)) != 1:
                raise DatabaseUnavailableError
    except SQLAlchemyError:
        raise DatabaseUnavailableError from None
    logger.info(
        "database.readiness.completed",
        extra={
            "dependency": "database",
            "duration_ms": (perf_counter() - started) * 1000,
        },
    )
