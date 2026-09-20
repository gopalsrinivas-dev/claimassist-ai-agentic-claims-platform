from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import router as api_v1_router
from app.core.config import Settings
from app.main import create_app


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_tracks_startup_and_shutdown(app: FastAPI) -> None:
    client = TestClient(app)
    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200
    with client:
        assert client.get("/ready").status_code == 200
        assert client.get("/ready").json() == {"status": "ready"}
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert response.json()["error"]["correlation_id"] == response.headers["X-Correlation-ID"]


def test_liveness_survives_not_ready(app: FastAPI, client: TestClient) -> None:
    app.state.ready = False
    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200


def test_operational_routes_only(client: TestClient) -> None:
    assert set(client.get("/openapi.json").json()["paths"]) == {"/health", "/ready"}
    assert client.get("/api/v1/claims").status_code == 404


def test_factory_uses_configured_api_prefix() -> None:
    async def probe() -> dict[str, str]:
        return {"status": "test-only"}

    original_routes = list(api_v1_router.routes)
    try:
        api_v1_router.add_api_route("/probe", probe)
        configured_app = create_app(Settings(api_v1_prefix="/custom/v1", app_name="Test App"))
        with TestClient(configured_app) as client:
            assert client.get("/custom/v1/probe").status_code == 200
            assert client.get("/api/v1/probe").status_code == 404
            assert client.get("/health").status_code == 200
            assert client.get("/openapi.json").json()["info"]["title"] == "Test App"
    finally:
        api_v1_router.routes[:] = original_routes
