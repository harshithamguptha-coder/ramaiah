"""Dataset ingestion: validation, storage, structural profiling.

Replace ``profile_dataset`` with a real parser/profiler (pandas, Polars, pyarrow)
here — no other module needs to change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import UploadFile

from config import settings
from models.mock import build_dataset_block, build_problem_block
from utils.file_utils import (
    ensure_directory,
    sanitize_filename,
    validate_extension,
    validate_size,
)
from utils.ids import new_file_id, utc_now_iso
from utils.logging_config import get_logger
from utils.profiling import profile_dataset

logger = get_logger(__name__)


async def store_upload(file: UploadFile) -> dict[str, Any]:
    """Persist an uploaded dataset and return its metadata.

    Raises ``HTTPException`` for unsupported types or oversized files.
    """
    extension = validate_extension(file.filename or "", settings.allowed_extensions)
    raw_name = sanitize_filename(file.filename or "dataset")

    directory = ensure_directory(settings.upload_dir)
    file_id = new_file_id()
    destination = directory / f"{file_id}_{raw_name}"

    content = await file.read()
    validate_size(len(content), settings.max_upload_bytes)
    destination.write_bytes(content)

    metadata = {
        "file_id": file_id,
        "file_name": raw_name,
        "file_size_bytes": len(content),
        "file_type": extension.lstrip("."),
        "uploaded_at": utc_now_iso(),
        "stored_path": str(destination),
    }
    logger.info("Stored upload %s (%s bytes)", metadata["file_name"], metadata["file_size_bytes"])
    return metadata


def build_dataset(metadata: dict[str, Any]) -> dict[str, Any]:
    """Read the stored file and return the dataset block for an analysis."""
    stored_path = metadata.get("stored_path")
    content = b""
    size = metadata.get("file_size_bytes", 0)

    if stored_path and Path(stored_path).exists():
        try:
            content = Path(stored_path).read_bytes()
            size = len(content) or size
        except OSError as exc:  # noqa: PERF203 - defensive, must not break the flow
            logger.warning("Could not read %s: %s", stored_path, exc)

    extension = f".{metadata.get('file_type', 'csv')}"
    profile = profile_dataset(content, extension, size)
    return build_dataset_block(metadata, profile)


def build_problem(description: str, dataset: dict[str, Any]) -> dict[str, Any]:
    """Return the problem-classification block."""
    return build_problem_block(description, dataset)
