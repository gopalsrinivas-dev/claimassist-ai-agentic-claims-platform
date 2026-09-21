"""Migrations use application settings and the shared engine constructor."""

import logging

from alembic.util import CommandError
from pydantic import ValidationError
from pydantic_settings import SettingsError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from alembic import context
from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_database_engine
from app.observability.logging import configure_logging


def run_migrations() -> None:
    try:
        settings = Settings()
    except (ValidationError, SettingsError):
        raise CommandError("Invalid application database configuration.") from None
    configure_logging(settings.log_level)
    try:
        if context.is_offline_mode():
            context.configure(
                url=make_url(settings.database_url.get_secret_value()).set(
                    drivername="postgresql+psycopg"
                ),
                target_metadata=Base.metadata,
                literal_binds=True,
                dialect_opts={"paramstyle": "named"},
            )
            with context.begin_transaction():
                context.run_migrations()
        else:
            engine = create_database_engine(settings)
            try:
                with engine.connect() as connection:
                    context.configure(connection=connection, target_metadata=Base.metadata)
                    with context.begin_transaction():
                        context.run_migrations()
            finally:
                engine.dispose()
    except SQLAlchemyError:
        logging.getLogger("claimassist.database").error(
            "database.migration.failed",
            extra={"dependency": "database", "error_code": "DATABASE_UNAVAILABLE"},
        )
        raise CommandError("Database migration failed; check database availability.") from None


run_migrations()
