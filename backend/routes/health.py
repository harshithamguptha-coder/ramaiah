"""Health and service-metadata routes."""

from __future__ import annotations

from fastapi import APIRouter

from config import settings
from models.schemas import HealthResponse
from services import quantum_service
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
        mode="real",
        time=utc_now_iso(),
    )


@router.get("/meta", summary="API capabilities")
def meta() -> dict:
    """Describe what the API currently supports, so the UI can adapt."""
    framework = quantum_service.available_framework()
    return {
        "analysis_mode": "real",
        "mock_data": False,
        "supported_formats": [ext.lstrip(".") for ext in settings.allowed_extensions],
        "max_upload_mb": settings.max_upload_bytes // (1024 * 1024),
        "max_analysis_rows": settings.analysis_max_rows,
        "implemented": [
            "upload",
            "dataset-profiling",
            "problem-characterization",
            "classical-model-training",
            "local-qiskit-qaoa-execution",
            "comparison",
            "recommendation-engine",
            "report-generation",
        ],
        "not_implemented": [
            "quantum-hardware-execution",
            "measured-quantum-performance",
        ],
        "quantum": {
            "framework_available": framework,
            "framework": framework,
            "execution_mode": "local-qiskit-aer-simulation",
            "hardware_executed": False,
            "statement": (
                "A QAOA circuit is built from the dataset's feature-correlation graph and "
                "executed on a local Qiskit Aer simulator, so circuit metrics and objective "
                "values are measured. No quantum hardware is used and no quantum advantage "
                "is claimed."
            ),
        },
        "philosophy": (
            "Use quantum computing only when the problem characteristics justify "
            "investigating it."
        ),
    }
