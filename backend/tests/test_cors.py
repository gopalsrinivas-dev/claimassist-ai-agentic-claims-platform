import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

ORIGIN = "http://localhost:3000"


def test_allowed_origin_can_read_correlation_header() -> None:
    app = create_app(Settings(cors_allowed_origins=(ORIGIN,)))
    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": ORIGIN})
    assert response.headers["Access-Control-Allow-Origin"] == ORIGIN
    assert response.headers["Access-Control-Expose-Headers"] == "X-Correlation-ID"
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_credentials_are_explicitly_configured() -> None:
    app = create_app(Settings(cors_allowed_origins=(ORIGIN,), cors_allow_credentials=True))
    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": ORIGIN})
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert response.headers["Access-Control-Allow-Origin"] == ORIGIN


def test_unlisted_origin_is_not_allowed(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "https://untrusted.test"})
    assert "Access-Control-Allow-Origin" not in response.headers


@pytest.mark.parametrize(
    ("origin", "method", "header", "status"),
    [
        (ORIGIN, "GET", "X-Correlation-ID", 200),
        ("https://untrusted.test", "GET", "X-Correlation-ID", 400),
        (ORIGIN, "DELETE", "X-Correlation-ID", 400),
        (ORIGIN, "GET", "X-Unapproved", 400),
    ],
)
def test_preflight_allow_list(origin: str, method: str, header: str, status: int) -> None:
    app = create_app(Settings(cors_allowed_origins=(ORIGIN,)))
    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": header,
            },
        )
    assert response.status_code == status
    assert "X-Correlation-ID" in response.headers
    if status == 400:
        assert response.json()["error"]["code"] == "CORS_REJECTED"
        assert response.json()["error"]["correlation_id"] == response.headers["X-Correlation-ID"]


def test_unexpected_errors_retain_cors_headers() -> None:
    app = create_app(Settings(cors_allowed_origins=(ORIGIN,)))

    @app.get("/failure")
    async def failure() -> None:
        raise RuntimeError("synthetic failure")

    with TestClient(app) as client:
        response = client.get("/failure", headers={"Origin": ORIGIN})
    assert response.status_code == 500
    assert response.headers["Access-Control-Allow-Origin"] == ORIGIN
    assert response.json()["error"]["correlation_id"] == response.headers["X-Correlation-ID"]
