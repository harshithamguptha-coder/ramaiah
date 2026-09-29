"""Q-Compass FastAPI application entry point.

Run with::

    cd backend
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from routes import analysis, health, upload
from utils.file_utils import ensure_directory
from utils.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001 - FastAPI signature
    """Prepare and tear down application resources."""
    ensure_directory(settings.upload_dir)
    logger.info("%s v%s starting in %s mode", settings.app_name, settings.app_version, settings.environment)
    logger.info("Quantum analysis uses a local Qiskit Aer simulator; other analysis stages remain mocked.")
    yield
    logger.info("%s shutting down", settings.app_name)


DESCRIPTION = """
**Q-Compass** — Quantum Readiness & AI Decision Engine.

Upload a dataset, describe the AI problem, and Q-Compass compares Classical AI,
Quantum AI and Hybrid AI approaches for it.

> **Prototype status:** dataset ingestion, structural profiling, and the
> quantum feature-selection experiment are real. Classical comparison and
> recommendation stages still contain mock data.
> The response contract is final, so the engines can be replaced independently.
"""


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(upload.router)
    app.include_router(analysis.router)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        """Minimal landing payload pointing at the docs and health check."""
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "mode": "mixed",
            "docs": "/docs",
            "health": "/api/health",
        }

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Return a consistent JSON error shape for unexpected failures."""
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error.",
                "path": request.url.path,
                "error_type": type(exc).__name__,
            },
        )

    return app


app = create_app()
