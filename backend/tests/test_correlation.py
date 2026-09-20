import asyncio
from uuid import UUID, uuid4

import httpx2 as httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.observability.context import get_correlation_id


def test_generates_unique_ids(client: TestClient) -> None:
    ids = [client.get("/health").headers["X-Correlation-ID"] for _ in range(2)]
    assert all(UUID(value).version == 4 for value in ids)
    assert ids[0] != ids[1]


def test_accepts_valid_incoming_id(client: TestClient) -> None:
    incoming = str(uuid4())
    response = client.get("/health", headers={"x-correlation-id": incoming.upper()})
    assert response.headers["X-Correlation-ID"] == incoming


@pytest.mark.parametrize(
    "value",
    ["", "bad-id", "a" * 2048, "secret\r\ninjected", "00000000-0000-0000-0000-000000000000"],
)
def test_invalid_incoming_id_is_replaced(client: TestClient, value: str) -> None:
    response = client.get("/health", headers={"X-Correlation-ID": value})
    assert response.status_code == 200
    assert UUID(response.headers["X-Correlation-ID"]).version == 4
    assert response.headers["X-Correlation-ID"] != value


def test_duplicate_ids_are_replaced(client: TestClient) -> None:
    incoming = str(uuid4())
    response = client.get(
        "/health", headers=[("X-Correlation-ID", incoming), ("X-Correlation-ID", incoming)]
    )
    assert response.headers["X-Correlation-ID"] != incoming


def test_context_is_available_and_isolated_for_concurrent_requests(app: FastAPI) -> None:
    @app.get("/context")
    async def context(request: Request) -> dict[str, str | None]:
        before = get_correlation_id()
        await asyncio.sleep(0)
        return {
            "before": before,
            "after": get_correlation_id(),
            "state": request.state.correlation_id,
        }

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            incoming = [str(uuid4()) for _ in range(8)]
            responses = await asyncio.gather(
                *(client.get("/context", headers={"X-Correlation-ID": value}) for value in incoming)
            )
        for response, value in zip(responses, incoming, strict=True):
            assert response.json() == {"before": value, "after": value, "state": value}
            assert response.headers["X-Correlation-ID"] == value
        assert get_correlation_id() is None

    asyncio.run(exercise())
