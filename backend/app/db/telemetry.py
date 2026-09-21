"""Database telemetry never records statements, parameters, URLs or driver messages."""

import logging
from time import perf_counter

from sqlalchemy import Connection, Engine, event
from sqlalchemy.engine import ExceptionContext, ExecutionContext

logger = logging.getLogger("claimassist.database")


def configure_database_logging() -> None:
    # Third-party pool/engine logs may include exception text or SQL literals.
    for name in ("sqlalchemy", "sqlalchemy.engine", "sqlalchemy.pool", "psycopg"):
        dependency_logger = logging.getLogger(name)
        dependency_logger.handlers.clear()
        dependency_logger.addHandler(logging.NullHandler())
        dependency_logger.propagate = False
        dependency_logger.setLevel(logging.CRITICAL + 1)


def install_query_telemetry(engine: Engine) -> None:
    def before(
        conn: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        conn.info["claimassist_query_started"] = perf_counter()

    def after(
        conn: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        started = conn.info.pop("claimassist_query_started", perf_counter())
        logger.info(
            "database.query.completed",
            extra={
                "dependency": "database",
                "duration_ms": (perf_counter() - started) * 1000,
            },
        )

    def failed(context: ExceptionContext) -> None:
        # Error mapping belongs to the application boundary, not this event hook.
        if context.connection is not None:
            context.connection.info.pop("claimassist_query_started", None)

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    event.listen(engine, "handle_error", failed)
