"""Stage 1-2a — dataset ingestion, storage and structural profiling.

Responsibilities:

* validate the upload (extension, size) and write it to disk
* parse it into a DataFrame exactly once and cache that frame for later stages
* emit the ``dataset`` block the frontend already consumes

Every key the existing UI reads is preserved (``rows``, ``column_count``,
``numerical_features``, ``categorical_features``, ``missing_values``,
``target_column``, ``feature_names``, ``profile_method``, ...). The deeper
statistics required by the decision engine are *added* alongside them rather
than replacing them, so no frontend change is needed to surface them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import UploadFile

from config import settings
from utils.dataset_cache import put_frame
from utils.errors import AnalysisError
from utils.file_utils import (
    ensure_directory,
    sanitize_filename,
    validate_extension,
    validate_size,
)
from utils.formatting import human_file_size
from utils.ids import new_file_id, utc_now_iso
from utils.logging_config import get_logger
from utils.profiling import empty_profile, load_dataframe, profile_dataframe

logger = get_logger(__name__)


async def store_upload(file: UploadFile) -> dict[str, Any]:
    """Persist an uploaded dataset and return its metadata.

    Raises ``HTTPException`` (via ``utils.file_utils``) for unsupported types or
    oversized files.
    """
    extension = validate_extension(file.filename or "", settings.allowed_extensions)
    raw_name = sanitize_filename(file.filename or "dataset")

    directory = ensure_directory(settings.upload_dir)
    file_id = new_file_id()
    destination = directory / f'{file_id}_{raw_name}'

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
    logger.info("Stored upload %s (%s bytes)", metadata['file_name'], metadata['file_size_bytes'])
    return metadata


def build_dataset(
    metadata: dict[str, Any],
    *,
    target_column: str | None = None,
    problem_description: str = "",
) -> dict[str, Any]:
    """Read the stored file and return the dataset block for an analysis.

    Parsing failures are *captured*, not raised: the block still comes back,
    flagged, so the pipeline can explain the problem instead of returning a
    bare 500. Callers that need the hard failure read ``block['parse_error']``.
    """
    stored_path = metadata.get("stored_path")
    size = metadata.get("file_size_bytes", 0) or 0
    extension = f'.{metadata.get("file_type", "csv")}'
    target = target_column or metadata.get("target_column")

    try:
        if not stored_path or not Path(stored_path).exists():
            raise FileNotFoundError(stored_path or "<no path>")
        frame = load_dataframe(stored_path, extension)
        profile = profile_dataframe(
            frame,
            target_column=target,
            file_size_bytes=size,
            description=problem_description,
        )
        # Cache for classical_service so the file is parsed only once.
        put_frame(metadata.get("file_id"), frame)
    except AnalysisError as exc:
        logger.warning("Could not parse %s: %s", metadata.get("file_name"), exc.message)
        profile = empty_profile(exc.error_code)
        block = _build_block(metadata, profile)
        block["parse_error"] = exc.to_payload()
        return block
    except OSError:
        logger.warning("Could not read %s", stored_path)
        profile = empty_profile("file_unreadable")
        block = _build_block(metadata, profile)
        block["parse_error"] = {
            "error_code": "file_unreadable",
            "detail": (
                "The stored file for this analysis is no longer available. "
                "Re-upload the dataset to run the analysis again."
            ),
        }
        return block
    except Exception as exc:  # noqa: BLE001 - never 500 on a bad upload
        logger.exception("Unexpected error parsing %s", metadata.get("file_name"))
        profile = empty_profile(type(exc).__name__)
        block = _build_block(metadata, profile)
        block["parse_error"] = {
            "error_code": "parse_error",
            "detail": f"The dataset could not be parsed ({type(exc).__name__}).",
        }
        return block

    return _build_block(metadata, profile)



def _build_block(metadata: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Assemble the ``dataset`` block.

    The first section is the contract the existing frontend already renders; the
    second is the richer structural detail the decision engine consumes and the
    report surfaces.
    """
    size = metadata.get("file_size_bytes", 0) or 0
    columns = profile.get("column_names") or []
    features = profile.get("feature_names") or []
    rows = profile.get("rows") or 0

    return {
        # --- existing frontend contract (names unchanged) ---
        "file_id": metadata.get("file_id"),
        "file_name": metadata.get("file_name"),
        "file_size_bytes": size,
        "file_size_display": human_file_size(size),
        "file_type": metadata.get("file_type"),
        "uploaded_at": metadata.get("uploaded_at", utc_now_iso()),
        "rows": profile.get("rows"),
        "column_count": len(columns),
        "column_names": columns,
        "numerical_features": profile.get("numerical_features"),
        "categorical_features": profile.get("categorical_features"),
        "missing_values": profile.get("missing_values"),
        "missing_percent": profile.get("missing_percent"),
        "target_column": profile.get("target_column"),
        "feature_names": features[:12],
        "feature_count": len(features),
        "memory_footprint_mb": profile.get("memory_footprint_mb"),
        "profile_method": profile.get("profile_method"),
        "profiled": bool(rows),
        "is_mock": False,
        # --- extended structural profile ---
        "numerical_columns": profile.get("numerical_columns", []),
        "categorical_columns": profile.get("categorical_columns", []),
        "datetime_features": profile.get("datetime_features", 0),
        "duplicate_rows": profile.get("duplicate_rows"),
        "duplicate_percent": profile.get("duplicate_percent"),
        "columns_with_missing": profile.get("columns_with_missing"),
        "class_distribution": profile.get("class_distribution"),
        "class_count": profile.get("class_count"),
        "target_source": profile.get("target_source"),
        "target_candidates": profile.get("target_candidates", []),
        "feature_cardinality": profile.get("feature_cardinality", {}),
        "mean_cardinality": profile.get("mean_cardinality"),
        "high_cardinality_features": profile.get("high_cardinality_features", []),
        "id_like_features": profile.get("id_like_features", []),
        "feature_to_sample_ratio": profile.get("feature_to_sample_ratio"),
        "estimated_search_space": profile.get("estimated_search_space"),
        "estimated_search_space_log2": profile.get("estimated_search_space_log2"),
        "dataset_size_mb": profile.get("dataset_size_mb"),
        "size_label": profile.get("size_label"),
        "problem_type": profile.get("problem_type", "unknown"),
        "sampled": profile.get("sampled", False),
        "warnings": profile.get("warnings", []),
        "note": (
            "Read directly from your file with pandas. "
            f'Method: {profile.get("profile_method")}.'
        ),
    }
