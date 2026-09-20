"""Keep rejected CORS preflights in the same safe API error envelope."""

import logging
from uuid import uuid4

from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.api.errors import error_response
from app.observability.context import get_correlation_id

logger = logging.getLogger("claimassist.cors")


class ApiCORSMiddleware(CORSMiddleware):
    def preflight_response(self, request_headers: Headers) -> Response:
        response = super().preflight_response(request_headers)
        if response.status_code < 400:
            return response
        logger.warning("request.error", extra={"error_code": "CORS_REJECTED", "status_code": 400})
        result = error_response(
            get_correlation_id() or str(uuid4()),
            400,
            "CORS_REJECTED",
            "The cross-origin request is not allowed.",
        )
        for name, value in response.headers.items():
            if name.startswith("access-control-") or name == "vary":
                result.headers[name] = value
        return result
