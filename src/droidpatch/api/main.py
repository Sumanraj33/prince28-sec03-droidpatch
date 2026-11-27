"""FastAPI application factory for DroidPatch."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from droidpatch.api.errors import http_exception_handler, validation_exception_handler
from droidpatch.api.middleware import add_request_context
from droidpatch.api.routes import chat, ingest
from droidpatch.api.routes.documents import router as documents_router
from droidpatch.api.routes.health import router as health_router
from droidpatch.config import Settings, get_settings
from droidpatch.db.database import SessionLocal, engine
from droidpatch.db.llm_calls import make_recorder
from droidpatch.llm.gateway import build_gateway
from droidpatch.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings or get_settings()
    setup_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage database engine and optional embedded worker lifecycle."""
        logger.info("DroidPatch API starting")
        logger.info(
            "database_pool_status",
            extra={"pool_status": engine.pool.status()},
        )
        worker = None
        if settings.worker_in_api:
            from droidpatch.workers.main import run_embedded

            worker = asyncio.create_task(run_embedded(settings))
        yield
        if worker:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
        if getattr(app.state, "queue", None):
            await app.state.queue.close()
        await engine.dispose()
        logger.info("DroidPatch API stopped")

    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = SessionLocal
    app.state.system_prompt = chat.load_prompt(settings.prompts_dir)
    app.state.gateway = build_gateway(settings, make_recorder(SessionLocal))

    app.middleware("http")(add_request_context)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    v1 = APIRouter(prefix="/v1")
    v1.include_router(chat.router)
    v1.include_router(ingest.router)

    app.include_router(health_router)
    app.include_router(documents_router)
    app.include_router(v1)

    return app
