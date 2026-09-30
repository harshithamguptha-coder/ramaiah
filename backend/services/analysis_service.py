"""Pipeline orchestrator.

Owns the stage order and the single canonical payload shape::

    upload -> profiling -> problem -> classical -> quantum -> comparison
          -> recommendation -> report

Each stage is delegated to its own service module, so stages can be replaced or
reordered independently. The orchestrator is the only place that knows the whole
sequence.

Stage isolation
---------------
Stages 3-6 all need the parsed DataFrame. Rather than re-reading the file four
times, :mod:`utils.dataset_cache` holds the single parse, and every stage is
handed the same object. If that cache misses (for example the process was
restarted), stages degrade to a flagged ``skipped`` block rather than failing
the request.

Stage failures are captured, not propagated: a broken stage produces a block
that explains itself and the pipeline still returns a complete, renderable
payload, because a partial report is more useful to a user than a 500.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from models.mock.pipeline import build_pipeline
from services import (
    classical_service,
    comparison_service,
    dataset_service,
    problem_service,
    quantum_service,
    recommendation_service,
    report_service,
)
from utils.dataset_cache import drop_frame, get_frame
from utils.ids import new_analysis_id, utc_now_iso
from utils.logging_config import get_logger
from utils.store import get_repository

logger = get_logger(__name__)


def _safe(stage: str, fn, *args, **kwargs) -> dict[str, Any]:
    """Run a stage, converting a crash into a self-describing block.

    A typed :class:`~utils.errors.AnalysisError` is *not* caught here: those are
    deliberate, user-facing conditions (an over-long problem statement, an
    unparseable file) that already carry the right HTTP status, and silently
    degrading them into a 200 would hide a real problem from the caller.
    Unexpected exceptions are caught, so a bug in one stage cannot 500 the run.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - never 500 mid-pipeline
        logger.exception("Stage %s raised", stage)
        return {
            "status": "failed",
            "errors": [f"{stage} failed unexpectedly ({type(exc).__name__})."],
            "note": f"{stage} failed.",
        }


def run_pipeline(
    metadata: dict[str, Any],
    problem_description: str,
    analysis_id: str | None = None,
    target_column: str | None = None,
) -> dict[str, Any]:
    """Execute every stage and return the full analysis payload."""
    analysis_id = analysis_id or new_analysis_id()

    dataset = dataset_service.build_dataset(
        metadata,
        target_column=target_column,
        problem_description=problem_description or "",
    )
    frame = get_frame(dataset.get("file_id"))

    problem = _safe(
        "problem characterization",
        problem_service.build_problem,
        problem_description,
        dataset,
        frame,
    )
    classical = _safe("classical baseline", classical_service.run, dataset, problem, analysis_id, frame)
    # The QAOA stage reads the stored file itself (it needs the raw rows to build a
    # feature-correlation graph), so it is handed the upload metadata rather than the
    # shared DataFrame every other stage uses.
    quantum = _safe("quantum suitability", quantum_service.run, dataset, problem, analysis_id, metadata)
    comparison = _safe("comparison", comparison_service.run, classical, quantum, dataset, analysis_id)
    recommendation = _safe(
        "recommendation",
        recommendation_service.run,
        comparison,
        classical,
        quantum,
        problem,
        dataset,
        analysis_id,
    )

    payload: dict[str, Any] = {
        "analysis_id": analysis_id,
        "status": "completed",
        "created_at": utc_now_iso(),
        "data_source": "real",
        "mock_data": False,
        # True only when the QAOA stage actually executed a circuit locally.
        "quantum_analysis_real": quantum.get("quantum_analysis_real", False),
        "problem_description": problem_description or "",
        "file_metadata": metadata,
        "pipeline": build_pipeline(completed_through="report"),
        "dataset": dataset,
        "problem": problem,
        "classical_analysis": classical,
        "quantum_analysis": quantum,
        "comparison": comparison,
        "recommendation": recommendation,
    }
    payload["warnings"] = collect_warnings(payload)
    payload["report"] = report_service.run(payload)
    return payload


def collect_warnings(payload: dict[str, Any]) -> list[str]:
    """Flatten the per-stage warnings into one de-duplicated list."""
    out: list[str] = []
    for key in ("dataset", "problem", "classical_analysis", "quantum_analysis"):
        for warning in (payload.get(key) or {}).get("warnings", []) or []:
            if warning not in out:
                out.append(warning)
    for key in ("dataset", "problem", "classical_analysis"):
        error = (payload.get(key) or {}).get("parse_error")
        if error and error.get("detail") not in out:
            out.append(str(error.get("detail")))
    return out


def save(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist an analysis through the repository seam."""
    return get_repository().save(payload)


def create_stub(
    metadata: dict[str, Any], problem_description: str, target_column: str | None = None
) -> dict[str, Any]:
    """Create the lightweight record returned right after upload.

    The stub carries the stored file path so ``POST /api/analyze`` can pick the
    run up later without re-uploading.
    """
    analysis_id = new_analysis_id()
    # Remember what the user actually asked for: the *resolved* target must not
    # be fed back in on the next call, or it would be re-labelled "user-specified".
    metadata = {**metadata, "requested_target_column": target_column}
    dataset = dataset_service.build_dataset(
        metadata,
        target_column=target_column,
        problem_description=problem_description or "",
    )
    frame = get_frame(dataset.get("file_id"))
    problem = _safe(
        "problem characterization",
        problem_service.build_problem,
        problem_description or "",
        dataset,
        frame,
    )
    return save(
        {
            "analysis_id": analysis_id,
            "status": "uploaded",
            "created_at": utc_now_iso(),
            "data_source": "real",
            "mock_data": False,
            "problem_description": problem_description or "",
            "file_metadata": metadata,
            "pipeline": build_pipeline(completed_through="upload"),
            "dataset": dataset,
            "problem": problem,
        }
    )


def create_analysis(
    metadata: dict[str, Any],
    problem_description: str,
    target_column: str | None = None,
) -> dict[str, Any]:
    """Run the pipeline and store the result."""
    payload = run_pipeline(metadata, problem_description, target_column=target_column)
    stored = save(payload)
    logger.info("Analysis %s completed", stored["analysis_id"])
    return stored


def start_analysis(
    analysis_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    problem_description: str | None = None,
    target_column: str | None = None,
) -> dict[str, Any]:
    """Run the full pipeline for an existing upload, or a brand new analysis.

    Reuses ``analysis_id`` when continuing an upload so the URL the client
    already holds keeps resolving to the same run.
    """
    if analysis_id:
        existing = get_analysis(analysis_id)
        metadata = existing.get("file_metadata") or metadata
        if metadata is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The stored file for this analysis is no longer available. "
                    "Re-upload the dataset to run the analysis again."
                ),
            )
        if problem_description is None:
            problem_description = existing.get("problem_description", "")
        if target_column is None:
            target_column = (existing.get("file_metadata") or {}).get(
                "requested_target_column"
            )
        return save(
            run_pipeline(
                metadata,
                problem_description,
                analysis_id=existing["analysis_id"],
                target_column=target_column,
            )
        )

    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide an 'analysis_id' from a previous upload.",
        )
    return create_analysis(metadata, problem_description or "", target_column=target_column)


def get_analysis(analysis_id: str) -> dict[str, Any]:
    """Return a stored analysis or raise 404."""
    record = get_repository().get(analysis_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found.",
        )
    return record


def list_analyses(limit: int = 10) -> list[dict[str, Any]]:
    """Return recent analyses, newest first."""
    return get_repository().list(limit=limit)


def delete_analysis(analysis_id: str) -> bool:
    """Delete an analysis; returns ``False`` when it did not exist.

    Also releases the cached DataFrame for that upload.
    """
    record = get_repository().get(analysis_id)
    if record is None:
        return False
    drop_frame((record.get("file_metadata") or {}).get("file_id"))
    return get_repository().delete(analysis_id)


def to_summary(record: dict[str, Any]) -> dict[str, Any]:
    """Project a full analysis down to the fields the dashboard list needs."""
    dataset = record.get("dataset", {})
    problem = record.get("problem", {})
    recommendation = record.get("recommendation", {})
    return {
        "analysis_id": record.get("analysis_id"),
        "created_at": record.get("created_at"),
        "file_name": dataset.get("file_name", "Unknown file"),
        "problem_description": record.get("problem_description", ""),
        "task_type": problem.get("task_type", "-"),
        "recommended_approach": recommendation.get("recommended_approach", "-"),
        "confidence": recommendation.get("confidence", 0),
        "status": record.get("status", "unknown"),
    }


def get_section(analysis_id: str, key: str) -> dict[str, Any]:
    """Return one block of a stored analysis (e.g. ``quantum_analysis``)."""
    record = get_analysis(analysis_id)
    if key not in record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown section '{key}'."
        )
    return record[key]
