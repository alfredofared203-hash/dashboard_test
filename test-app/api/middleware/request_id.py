import re
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.logging_config import request_id_context


REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        provided = headers.get(b"x-request-id", b"").decode("latin-1")
        request_id = provided if REQUEST_ID_PATTERN.fullmatch(provided) else str(uuid4())
        token = request_id_context.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_context.reset(token)
