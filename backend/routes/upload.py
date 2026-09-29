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
    summary="Upload a dataset and return basic file metadata",
)
async def upload_dataset(
    file: UploadFile = File(..., description="CSV, XLSX or JSON dataset"),
    problem_description: str | None = Form(
        default=None, description="Optional description of the AI problem"
    ),
) -> UploadResponse:
    """Accept a dataset, store it, and return metadata plus a stub analysis.

    This does **not** run the full pipeline — the client follows up with
    ``POST /api/analyze`` once the user presses "Start Analysis".
    """
    metadata = await dataset_service.store_upload(file)
    record = analysis_service.create_stub(metadata, problem_description or "")

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
