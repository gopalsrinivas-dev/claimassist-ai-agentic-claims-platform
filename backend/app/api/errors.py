"""One mapping boundary for application, framework, and unexpected errors."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.api.schemas import ErrorDetail, ErrorResponse
from app.core.exceptions import ClaimAssistError

logger = logging.getLogger("claimassist.errors")

HTTP_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "AUTHENTICATION_ERROR",
    403: "AUTHORIZATION_ERROR",
    404: "RESOURCE_NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    503: "DEPENDENCY_UNAVAILABLE",
}


def error_response(correlation_id: str, status: int, code: str, message: str) -> JSONResponse:
    envelope = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            correlation_id=correlation_id,
        )
    )
    return JSONResponse(envelope.model_dump(mode="json"), status_code=status)


async def application_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ClaimAssistError)
    logger.warning("request.error", extra={"error_code": exc.code, "status_code": exc.status_code})
    return error_response(request.state.correlation_id, exc.status_code, exc.code, exc.message)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Even field names, validator context and invalid values may contain private data.
    logger.warning("request.error", extra={"error_code": "VALIDATION_ERROR", "status_code": 422})
    return error_response(
        request.state.correlation_id, 422, "VALIDATION_ERROR", "The request is invalid."
    )


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    code = HTTP_ERROR_CODES.get(exc.status_code, "HTTP_ERROR")
    try:
        message = HTTPStatus(exc.status_code).phrase
    except ValueError:
        message = "The request could not be completed."
    logger.warning("request.error", extra={"error_code": code, "status_code": exc.status_code})
    response = error_response(request.state.correlation_id, exc.status_code, code, message)
    # Keep protocol-relevant, server-authored headers; never reflect arbitrary detail.
    for name, value in (exc.headers or {}).items():
        if name.lower() in {"allow", "www-authenticate", "retry-after"}:
            response.headers[name] = value
    return response


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "request.error",
        extra={"error_code": "INTERNAL_ERROR", "status_code": 500},
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return error_response(
        request.state.correlation_id, 500, "INTERNAL_ERROR", "An unexpected error occurred."
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ClaimAssistError, application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
