from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from app.core.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ClaimAssistError,
    ConflictError,
    DependencyError,
    ResourceNotFoundError,
    ValidationError,
)
from app.main import create_app
from app.observability.context import get_correlation_id


@pytest.mark.parametrize(
    ("error_type", "status", "code"),
    [
        (ClaimAssistError, 400, "APPLICATION_ERROR"),
        (ValidationError, 422, "VALIDATION_ERROR"),
        (AuthenticationError, 401, "AUTHENTICATION_ERROR"),
        (AuthorizationError, 403, "AUTHORIZATION_ERROR"),
        (ResourceNotFoundError, 404, "RESOURCE_NOT_FOUND"),
        (ConflictError, 409, "CONFLICT"),
        (DependencyError, 503, "DEPENDENCY_UNAVAILABLE"),
    ],
)
def test_expected_errors(
    app: FastAPI, error_type: type[ClaimAssistError], status: int, code: str
) -> None:
    @app.get("/failure")
    async def failure() -> None:
        raise error_type("SYNTHETIC_PRIVATE_DIAGNOSTIC")

    correlation_id = str(uuid4())
    with TestClient(app) as client:
        response = client.get("/failure", headers={"X-Correlation-ID": correlation_id})
    assert response.status_code == status
    assert response.json() == {
        "error": {
            "code": code,
            "message": error_type.message,
            "details": {},
            "correlation_id": correlation_id,
        }
    }
    assert response.headers["X-Correlation-ID"] == correlation_id
    assert "SYNTHETIC_PRIVATE_DIAGNOSTIC" not in response.text


class InputPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int


@pytest.mark.parametrize(
    "payload",
    [{"count": "SYNTHETIC_PRIVATE_VALUE"}, {"count": 1, "SYNTHETIC_PRIVATE_KEY": "value"}],
)
def test_request_validation_is_sanitized(app: FastAPI, payload: dict[str, object]) -> None:
    @app.post("/validate")
    async def validate(body: InputPayload) -> InputPayload:
        return body

    with TestClient(app) as client:
        response = client.post("/validate", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"] == {}
    assert "SYNTHETIC_PRIVATE" not in response.text


def test_malformed_json_is_sanitized(app: FastAPI) -> None:
    @app.post("/validate")
    async def validate(body: InputPayload) -> InputPayload:
        return body

    with TestClient(app) as client:
        response = client.post(
            "/validate", content='{"SYNTHETIC_PRIVATE', headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 422
    assert "SYNTHETIC_PRIVATE" not in response.text


@pytest.mark.parametrize(
    ("path", "method", "status"), [("/missing", "GET", 404), ("/health", "POST", 405)]
)
def test_framework_errors(client: TestClient, path: str, method: str, status: int) -> None:
    response = client.request(method, path)
    assert response.status_code == status
    assert response.json()["error"]["correlation_id"] == response.headers["X-Correlation-ID"]
    if status == 405:
        assert "GET" in response.headers["Allow"]


def test_http_exception_hides_detail_and_preserves_auth_header(app: FastAPI) -> None:
    @app.get("/unauthenticated")
    async def unauthenticated() -> None:
        raise HTTPException(
            401, "SYNTHETIC_PRIVATE", headers={"WWW-Authenticate": "Bearer", "X-Private": "secret"}
        )

    with TestClient(app) as client:
        response = client.get("/unauthenticated")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert "X-Private" not in response.headers
    assert "SYNTHETIC_PRIVATE" not in response.text


def test_unexpected_error_is_generic_even_in_debug_mode() -> None:
    app = create_app(Settings(debug=True))

    @app.get("/unexpected")
    async def unexpected() -> None:
        raise RuntimeError("SYNTHETIC_PRIVATE")

    with TestClient(app) as client:
        response = client.get("/unexpected")
        assert client.get("/health").status_code == 200
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "details": {},
            "correlation_id": response.headers["X-Correlation-ID"],
        }
    }
    assert get_correlation_id() is None


def test_response_validation_is_a_server_error(app: FastAPI) -> None:
    @app.get("/bad-response", response_model=InputPayload)
    async def bad_response() -> dict[str, str]:
        return {"count": "SYNTHETIC_PRIVATE"}

    with TestClient(app) as client:
        response = client.get("/bad-response")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "SYNTHETIC_PRIVATE" not in response.text
