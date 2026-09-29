"""Health and service-metadata routes."""

from __future__ import annotations

from fastapi import APIRouter

from config import settings
from models.schemas import HealthResponse
from utils.ids import utc_now_iso

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    """Return service health. Used by the frontend to detect API availability."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        mode="mock",
        time=utc_now_iso(),
    )


@router.get("/meta", summary="API capabilities")
def meta() -> dict:
    """Describe what the API currently supports, so the UI can adapt."""
    return {
        "analysis_mode": "mock",
        "mock_data": True,
        "supported_formats": [ext.lstrip(".") for ext in settings.allowed_extensions],
        "max_upload_mb": settings.max_upload_bytes // (1024 * 1024),
        "implemented": ["upload", "structural-profiling", "mock-analysis-pipeline"],
        "not_implemented": [
            "classical-model-training",
            "feature-selection",
            "quantum-circuit-execution",
            "recommendation-engine",
        ],
    }
