"""Separate process liveness from database connectivity readiness."""

from fastapi import APIRouter, Request

from app.api.schemas import ErrorResponse, StatusResponse
from app.core.exceptions import DependencyError
from app.db.health import check_database

router = APIRouter(tags=["Operations"])


@router.get("/health", response_model=StatusResponse)
async def health() -> StatusResponse:
    return StatusResponse(status="ok")


@router.get("/ready", response_model=StatusResponse, responses={503: {"model": ErrorResponse}})
def ready(request: Request) -> StatusResponse:
    if not request.app.state.ready:
        raise DependencyError
    check_database(request.app.state.db_engine)
    return StatusResponse(status="ready")
