import json
import logging
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import DependencyError
from app.main import create_app
from app.observability.logging import JsonFormatter, configure_logging


def events_from(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def test_lifecycle_and_request_logging(capsys: pytest.CaptureFixture[str]) -> None:
    app = create_app(Settings())
    correlation_id = str(uuid4())
    with TestClient(app) as client:
        client.get("/health", headers={"X-Correlation-ID": correlation_id})
    events = events_from(capsys.readouterr().out)
    assert [event["event"] for event in events] == [
        "application.startup",
        "request.started",
        "request.completed",
        "application.shutdown",
    ]
    for event in events[1:3]:
        assert event["correlation_id"] == correlation_id
        assert event["method"] == "GET"
        assert event["path"] == "/health"
    assert events[2]["status_code"] == 200
    assert isinstance(events[2]["duration_ms"], (int, float))
    assert events[2]["duration_ms"] >= 0
    assert events[2]["response_completed"] is True


def test_sensitive_data_never_enters_app_logs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(Settings(app_env="test"))

    @app.post("/failure/{identifier}")
    async def failure(identifier: str) -> None:
        raise RuntimeError("SYNTHETIC_PRIVATE_EXCEPTION")

    correlation_id = str(uuid4())
    with TestClient(app) as client:
        client.post(
            "/failure/SYNTHETIC_PRIVATE_PATH?token=SYNTHETIC_PRIVATE_QUERY",
            headers={
                "X-Correlation-ID": correlation_id,
                "Authorization": "Bearer SYNTHETIC_PRIVATE_AUTH",
                "Cookie": "session=SYNTHETIC_PRIVATE_COOKIE",
                "X-API-Key": "SYNTHETIC_PRIVATE_KEY",
            },
            json={"document": "SYNTHETIC_PRIVATE_BODY"},
        )
        client.get(
            "/SYNTHETIC_PRIVATE_UNKNOWN", headers={"X-Correlation-ID": "SYNTHETIC_PRIVATE_ID"}
        )
    output = capsys.readouterr().out
    assert "SYNTHETIC_PRIVATE" not in output
    errors = [event for event in events_from(output) if event.get("error_code") == "INTERNAL_ERROR"]
    assert len(errors) == 1
    assert errors[0]["correlation_id"] == correlation_id
    assert errors[0]["path"] == "/failure/{identifier}"
    assert errors[0]["exception_type"] == "RuntimeError"
    assert errors[0]["exception_frames"]


def test_expected_error_is_logged_once_without_raw_exception(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(Settings(app_env="test"))

    @app.get("/dependency")
    async def dependency() -> None:
        raise DependencyError("SYNTHETIC_PRIVATE_PROVIDER")

    with TestClient(app) as client:
        response = client.get("/dependency")
    output = capsys.readouterr().out
    events = events_from(output)
    errors = [event for event in events if event["event"] == "request.error"]
    assert len(errors) == 1
    assert errors[0]["error_code"] == "DEPENDENCY_UNAVAILABLE"
    assert errors[0]["correlation_id"] == response.headers["X-Correlation-ID"]
    assert "exception_frames" not in errors[0]
    assert "SYNTHETIC_PRIVATE" not in output


def test_log_configuration_is_idempotent_and_honors_level(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("WARNING")
    configure_logging("WARNING")
    logger = logging.getLogger("claimassist.test")
    logger.info("should.not.appear")
    logger.warning("test.warning")
    events = events_from(capsys.readouterr().out)
    assert len(events) == 1
    assert events[0]["event"] == "test.warning"


def test_formatter_drops_unapproved_extra_fields() -> None:
    record = logging.makeLogRecord(
        {"msg": "test.event", "authorization": "SYNTHETIC_PRIVATE", "body": "SYNTHETIC_PRIVATE"}
    )
    output = JsonFormatter().format(record)
    assert "SYNTHETIC_PRIVATE" not in output
    assert json.loads(output)["correlation_id"] is None
