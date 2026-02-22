from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app import __version__
from app.api.errors import (
    internal_error_handler,
    pricing_error_handler,
    validation_error_handler,
)
from app.api.middleware import BodySizeLimitMiddleware, RequestIdMiddleware
from app.api.routes import router
from app.constants import MAX_REQUEST_BODY_BYTES
from app.engine import BillingEngine, PricingError
from app.logging import configure_logging
from app.pricing import PricingRepository

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and graceful shutdown."""
    logger.info("startup", extra={"event": "startup", "version": __version__})
    yield
    logger.info("shutdown", extra={"event": "shutdown"})


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    configure_logging()

    app = FastAPI(
        title="LLM Pricing Registry & Estimation API",
        version=__version__,
        lifespan=lifespan,
    )

    repository = PricingRepository()
    engine = BillingEngine(repository=repository, engine_version=__version__)

    app.state.repository = repository
    app.state.engine = engine

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_body_bytes=MAX_REQUEST_BODY_BYTES,
    )
    app.include_router(router)

    app.add_exception_handler(PricingError, cast(Any, pricing_error_handler))
    app.add_exception_handler(
        RequestValidationError,
        cast(Any, validation_error_handler),
    )
    app.add_exception_handler(Exception, cast(Any, internal_error_handler))

    return app


app = create_app()
