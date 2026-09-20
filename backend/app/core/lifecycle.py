"""Readiness tracks the application lifecycle; no external services exist yet."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger("claimassist.lifecycle")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("application.startup", extra={"app_env": app.state.settings.app_env})
    app.state.ready = True
    try:
        yield
    finally:
        app.state.ready = False
        logger.info("application.shutdown", extra={"app_env": app.state.settings.app_env})
