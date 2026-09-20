"""Application factory: uvicorn app.main:create_app --factory --no-access-log."""

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.v1.router import router as api_v1_router
from app.core.config import Settings
from app.core.lifecycle import lifespan
from app.middleware.cors import ApiCORSMiddleware
from app.middleware.errors import ErrorBoundaryMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.observability.context import CORRELATION_HEADER
from app.observability.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    configure_logging(settings.log_level)
    # DEBUG never enables Starlette's traceback response pages.
    app = FastAPI(title=settings.app_name, debug=False, lifespan=lifespan)
    app.state.settings = settings
    app.state.ready = False
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    # Last added is outermost: context -> CORS -> error boundary -> routes.
    app.add_middleware(ErrorBoundaryMiddleware)
    app.add_middleware(
        ApiCORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allowed_methods,
        allow_headers=settings.cors_allowed_headers,
        expose_headers=[CORRELATION_HEADER],
    )
    app.add_middleware(RequestContextMiddleware)
    return app
