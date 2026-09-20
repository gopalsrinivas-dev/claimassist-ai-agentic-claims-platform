import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from starlette.responses import StreamingResponse
from starlette.types import Message

from app.core.config import Settings
from app.main import create_app
from app.observability.context import get_correlation_id


def test_failed_stream_is_not_replaced_or_logged_with_private_details(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app: FastAPI = create_app(Settings())

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"first"
            raise RuntimeError("SYNTHETIC_PRIVATE_STREAM")

        return StreamingResponse(chunks())

    messages: list[Message] = []

    async def exercise() -> None:
        async def receive() -> Message:
            return {"type": "http.request", "body": b""}

        async def send(message: Message) -> None:
            messages.append(message)

        with pytest.raises(RuntimeError, match="The response could not be completed"):
            await app(
                {
                    "type": "http",
                    "asgi": {"version": "3.0", "spec_version": "2.4"},
                    "method": "GET",
                    "path": "/stream",
                    "root_path": "",
                    "query_string": b"",
                    "headers": [],
                    "scheme": "http",
                    "server": ("test", 80),
                },
                receive,
                send,
            )
        assert get_correlation_id() is None

    asyncio.run(exercise())
    assert sum(message["type"] == "http.response.start" for message in messages) == 1
    output = capsys.readouterr().out
    assert "SYNTHETIC_PRIVATE_STREAM" not in output
    events = [json.loads(line) for line in output.splitlines()]
    assert sum(event["event"] == "request.error" for event in events) == 1
    assert events[-1]["response_completed"] is False
