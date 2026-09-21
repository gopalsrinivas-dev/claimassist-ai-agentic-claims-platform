"""Application-owned database resources; connectivity is checked by /ready."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.session import create_database_engine, create_session_factory

logger = logging.getLogger("claimassist.lifecycle")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("application.startup", extra={"app_env": app.state.settings.app_env})
    engine = create_database_engine(app.state.settings)
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.ready = True
    try:
        yield
    finally:
        app.state.ready = False
        engine.dispose()
        logger.info("application.shutdown", extra={"app_env": app.state.settings.app_env})
