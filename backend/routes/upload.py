"""Dataset upload routes."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile, status

from models.schemas import UploadResponse
from services import analysis_service, dataset_service
from utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["dataset"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a dataset and return its basic file metadata",
)
async def upload_dataset(
    file: UploadFile = File(..., description="CSV, XLSX or JSON dataset"),
    problem_description: str | None = Form(
        default=None,
        max_length=2000,
        description="Optional description of the AI problem (max 2000 characters)",
    ),
    target_column: str | None = Form(
        default=None,
        description=(
            "Optional target/label column. Omit to auto-detect from the column name."
        ),
    ),
) -> UploadResponse:
    """Accept a dataset, store it, profile it, and return a stub analysis.

    This does **not** run the full pipeline - the client follows up with
    ``POST /api/analyze`` once the user presses "Start Analysis". Profiling
    already happens here so the upload screen can show real shape information.
    """
    metadata = await dataset_service.store_upload(file)
    record = analysis_service.create_stub(metadata, problem_description or "", target_column)

    logger.info("Upload accepted: %s", metadata["file_name"])
    return UploadResponse(
        analysis_id=record["analysis_id"],
        status="uploaded",
        message=(
            f"'{metadata['file_name']}' received "
            f"({metadata['file_size_bytes']:,} bytes). Ready to start analysis."
        ),
        dataset=record["dataset"],
        problem=record["problem"],
        pipeline=record["pipeline"],
    )
