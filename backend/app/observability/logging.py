"""JSON events with an allow-list of fields and sanitized exception frames."""

import json
import logging
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

from app.observability.context import request_context

EVENT_FIELDS = (
    "status_code",
    "duration_ms",
    "response_completed",
    "error_code",
    "app_env",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        context = request_context.get()
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "correlation_id": context.correlation_id if context else None,
        }
        if context:
            payload.update(method=context.method, path=context.path)
        for field in EVENT_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            # Preserve diagnostic locations, never exception messages, locals, source,
            # chained provider errors, or absolute workstation paths.
            error_type, _, tb = record.exc_info
            payload["exception_type"] = error_type.__name__ if error_type else "Unknown"
            payload["exception_frames"] = [
                {"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
                for frame in traceback.extract_tb(tb)
            ]
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def configure_logging(level: str) -> None:
    """Own only the app logger; never enable verbose HTTP/dependency logging."""
    logger = logging.getLogger("claimassist")
    for existing in logger.handlers[:]:
        logger.removeHandler(existing)
        existing.close()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
