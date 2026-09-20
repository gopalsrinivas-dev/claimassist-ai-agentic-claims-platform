"""Request-local context, isolated across concurrent async requests."""

from contextvars import ContextVar
from dataclasses import dataclass

CORRELATION_HEADER = "X-Correlation-ID"


@dataclass(frozen=True)
class RequestContext:
    correlation_id: str
    method: str
    path: str


request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def get_correlation_id() -> str | None:
    context = request_context.get()
    return context.correlation_id if context else None
