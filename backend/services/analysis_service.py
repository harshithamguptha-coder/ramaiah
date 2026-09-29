"""Pipeline orchestrator.

Owns the stage order and the single canonical payload shape::

    upload -> profiling -> classical -> quantum -> comparison
          -> recommendation -> report

Each stage is delegated to its own service module, so stages can be replaced
or reordered independently. The orchestrator is the only place that knows the
whole sequence.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from models.mock import build_pipeline
from services import (
    classical_service,
    comparison_service,
    dataset_service,
    quantum_service,
    recommendation_service,
    report_service,
)
from utils.ids import new_analysis_id, utc_now_iso
from utils.logging_config import get_logger
from utils.store import get_repository

logger = get_logger(__name__)


def run_pipeline(
    metadata: dict[str, Any],
    problem_description: str,
    analysis_id: str | None = None,
) -> dict[str, Any]:
    """Execute every stage and return the full analysis payload."""
    analysis_id = analysis_id or new_analysis_id()

    dataset = dataset_service.build_dataset(metadata)
    problem = dataset_service.build_problem(problem_description, dataset)
    classical = classical_service.run(dataset, problem, analysis_id)
    quantum = quantum_service.run(dataset, problem, analysis_id, metadata)
    comparison = comparison_service.run(classical, quantum, dataset, analysis_id)
    recommendation = recommendation_service.run(
        comparison, classical, quantum, problem, dataset, analysis_id
    )

    payload: dict[str, Any] = {
        "analysis_id": analysis_id,
        "status": "completed",
        "created_at": utc_now_iso(),
        "data_source": "mixed",
        "mock_data": True,
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
    payload["report"] = report_service.run(payload)

    return payload


def save(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist an analysis through the repository seam."""
    return get_repository().save(payload)


def create_stub(metadata: dict[str, Any], problem_description: str) -> dict[str, Any]:
    """Create the lightweight record returned right after upload.

    The stub carries the stored file path so ``POST /api/analyze`` can pick the
    run up later without re-uploading.
    """
    analysis_id = new_analysis_id()
    dataset = dataset_service.build_dataset(metadata)
    problem = dataset_service.build_problem(problem_description or "", dataset)

    return save(
        {
            "analysis_id": analysis_id,
            "status": "uploaded",
            "created_at": utc_now_iso(),
            "data_source": "mock",
            "mock_data": True,
            "problem_description": problem_description or "",
            "file_metadata": metadata,
            "pipeline": build_pipeline(completed_through="upload"),
            "dataset": dataset,
            "problem": problem,
        }
    )


def create_analysis(metadata: dict[str, Any], problem_description: str) -> dict[str, Any]:
    """Run the pipeline and store the result."""
    payload = run_pipeline(metadata, problem_description or "")
    stored = save(payload)
    logger.info("Analysis %s completed (mock)", stored["analysis_id"])
    return stored


def start_analysis(
    analysis_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    problem_description: str | None = None,
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
        return save(
            run_pipeline(metadata, problem_description, analysis_id=existing["analysis_id"])
        )

    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide an 'analysis_id' from a previous upload.",
        )
    return create_analysis(metadata, problem_description or "")


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
    """Delete an analysis; returns ``False`` when it did not exist."""
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
        "task_type": problem.get("task_type", "—"),
        "recommended_approach": recommendation.get("recommended_approach", "—"),
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
