"""FastAPI application factory for DroidPatch."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from droidpatch.api.errors import http_exception_handler, validation_exception_handler
from droidpatch.api.middleware import add_request_context
from droidpatch.api.routes.documents import router as documents_router
from droidpatch.api.routes.health import router as health_router
from droidpatch.config import Settings, get_settings
from droidpatch.db.database import engine
from droidpatch.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings or get_settings()
    setup_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage database engine lifecycle."""
        logger.info("DroidPatch API starting")
        yield
        await engine.dispose()
        logger.info("DroidPatch API stopped")

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.middleware("http")(add_request_context)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    app.include_router(health_router)
    app.include_router(documents_router)

    return app
