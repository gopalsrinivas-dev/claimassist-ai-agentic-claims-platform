"""Place unexpected-error translation inside CORS and request context."""

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import unexpected_error_handler


class ErrorBoundaryMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def track_response(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, track_response)
        except Exception as exc:
            # This is the single translation boundary, not a swallowed failure.
            # A started stream cannot be replaced by a second HTTP response.
            response = await unexpected_error_handler(Request(scope), exc)
            if response_started:
                # Prevent the ASGI server from printing the original private message.
                raise RuntimeError("The response could not be completed.") from None
            await response(scope, receive, send)
