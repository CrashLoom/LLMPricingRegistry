from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.engine.exceptions import PricingError

logger = logging.getLogger(__name__)


def _get_request_id(request: Request) -> str | None:
    """Read request ID from request state when available."""
    return getattr(request.state, "request_id", None)


def build_error_payload(
    code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build a consistent API error payload envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


async def pricing_error_handler(
    request: Request,
    exc: PricingError,
) -> JSONResponse:
    """Convert a domain pricing error into an HTTP response."""
    request_id = _get_request_id(request)
    logger.info(
        "pricing_error",
        extra={
            "event": "pricing_error",
            "status_code": exc.status_code,
            "error_code": exc.code,
            "request_id": request_id,
        },
    )
    response = JSONResponse(
        status_code=exc.status_code,
        content=build_error_payload(exc.code, exc.message, exc.details),
    )
    if request_id:
        response.headers["X-Request-Id"] = request_id
    return response


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return a normalized response for request validation failures."""
    request_id = _get_request_id(request)
    response = JSONResponse(
        status_code=400,
        content=build_error_payload(
            "INVALID_REQUEST",
            "Request validation failed",
            {"validation_errors": exc.errors()},
        ),
    )
    if request_id:
        response.headers["X-Request-Id"] = request_id
    return response


async def internal_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a generic internal error response without leaking details."""
    request_id = _get_request_id(request)
    logger.exception(
        "internal_error",
        extra={
            "event": "internal_error",
            "status_code": 500,
            "error_code": "INTERNAL_ERROR",
            "request_id": request_id,
        },
    )
    response = JSONResponse(
        status_code=500,
        content=build_error_payload("INTERNAL_ERROR", "Internal server error"),
    )
    if request_id:
        response.headers["X-Request-Id"] = request_id
    return response
