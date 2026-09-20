"""Unversioned operational probes, with no business or infrastructure calls."""

from fastapi import APIRouter, Request

from app.api.schemas import ErrorResponse, StatusResponse
from app.core.exceptions import DependencyError

router = APIRouter(tags=["Operations"])


@router.get("/health", response_model=StatusResponse)
async def health() -> StatusResponse:
    return StatusResponse(status="ok")


@router.get("/ready", response_model=StatusResponse, responses={503: {"model": ErrorResponse}})
async def ready(request: Request) -> StatusResponse:
    if not request.app.state.ready:
        raise DependencyError
    return StatusResponse(status="ready")
