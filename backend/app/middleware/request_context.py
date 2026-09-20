"""Correlation IDs and request lifecycle telemetry without capturing payloads."""

import logging
import re
from time import perf_counter
from uuid import UUID, uuid4

from fastapi.routing import iter_route_contexts
from starlette.datastructures import Headers, MutableHeaders
from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability.context import CORRELATION_HEADER, RequestContext, request_context

logger = logging.getLogger("claimassist.requests")
UUID_PATTERN = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
HTTP_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"}


def correlation_id_from_headers(headers: Headers) -> str:
    values = headers.getlist(CORRELATION_HEADER)
    if len(values) == 1 and UUID_PATTERN.fullmatch(values[0]):
        parsed = UUID(values[0])
        if parsed.int != 0:
            return str(parsed)
    return str(uuid4())


def safe_request_path(scope: Scope) -> str:
    """Log route templates, excluding query strings, identifiers and unknown paths."""
    for route in iter_route_contexts(scope["app"].routes):
        if route.path is not None:
            match, _ = route.matches(scope)
            if match != Match.NONE:
                return route.path
    return "<unmatched>"


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = correlation_id_from_headers(Headers(scope=scope))
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        context = RequestContext(
            correlation_id=correlation_id,
            method=scope["method"] if scope["method"] in HTTP_METHODS else "OTHER",
            path=safe_request_path(scope),
        )
        token = request_context.set(context)
        started = perf_counter()
        status_code = 500
        response_completed = False

        async def send_with_context(message: Message) -> None:
            nonlocal status_code, response_completed
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[CORRELATION_HEADER] = correlation_id
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                response_completed = True

        try:
            logger.info("request.started")
            await self.app(scope, receive, send_with_context)
        finally:
            logger.info(
                "request.completed",
                extra={
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                    "response_completed": response_completed,
                },
            )
            request_context.reset(token)
