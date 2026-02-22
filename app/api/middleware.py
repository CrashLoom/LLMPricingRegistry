from __future__ import annotations

import uuid

from fastapi.responses import JSONResponse
from starlette.middleware import base as middleware_base
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.api.errors import build_error_payload

REQUEST_ID_HEADER = "X-Request-Id"


class RequestIdMiddleware(middleware_base.BaseHTTPMiddleware):
    """Attach a unique request ID to every request and response."""

    async def dispatch(
        self,
        request: Request,
        call_next: middleware_base.RequestResponseEndpoint,
    ) -> Response:
        """Attach or generate a request ID and set it on the response."""
        header_request_id = request.headers.get(REQUEST_ID_HEADER)
        request_id = header_request_id or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _payload_too_large(max_bytes: int, actual: int) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content=build_error_payload(
            "INVALID_REQUEST",
            "Request body exceeds 1MB limit",
            {"max_body_bytes": max_bytes, "content_length": actual},
        ),
    )


def _parse_content_length(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


class BodySizeLimitMiddleware(middleware_base.BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        """Create a middleware instance enforcing maximum request size."""
        super().__init__(app)
        self._max_body_bytes = max_body_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: middleware_base.RequestResponseEndpoint,
    ) -> Response:
        """Reject over-sized API requests before they hit route handlers."""
        if not self._should_check(request):
            return await call_next(request)

        cl = _parse_content_length(request.headers.get("content-length"))
        if cl is not None and cl > self._max_body_bytes:
            return _payload_too_large(self._max_body_bytes, cl)

        body = await request.body()
        if len(body) > self._max_body_bytes:
            return _payload_too_large(self._max_body_bytes, len(body))

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": body, "more_body": False}

        return await call_next(Request(request.scope, receive))

    @staticmethod
    def _should_check(request: Request) -> bool:
        return request.method in {
            "POST",
            "PUT",
            "PATCH",
        } and request.url.path.startswith("/v1/")
