"""FastAPI application factory for DroidPatch."""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from droidpatch.api.errors import http_exception_handler, validation_exception_handler
from droidpatch.api.middleware import add_request_context
from droidpatch.api.routes.documents import router as documents_router
from droidpatch.api.routes.health import router as health_router
from droidpatch.config import Settings, get_settings
from droidpatch.logging_setup import setup_logging
from droidpatch.store import load_records

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings or get_settings()
    setup_logging(settings)

    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.state.settings = settings
    app.state.records = []
    app.state.records_loaded = False

    app.middleware("http")(add_request_context)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    app.include_router(health_router)
    app.include_router(documents_router)

    @app.on_event("startup")
    async def startup() -> None:
        try:
            app.state.records = load_records(settings.data_file)
            app.state.records_loaded = True
            logger.info("records loaded", extra={"records": len(app.state.records)})
        except FileNotFoundError:
            app.state.records = []
            app.state.records_loaded = False
            logger.warning("records file missing", extra={"path": str(settings.data_file)})
        except ValueError as exc:
            app.state.records = []
            app.state.records_loaded = False
            logger.warning("could not load records: %s", exc)

    return app
