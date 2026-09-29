"""Analysis lifecycle routes: run, fetch, list, delete, and download a report."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from models.schemas import (
    AnalysisListResponse,
    AnalysisSummary,
    AnalyzeRequest,
    MessageResponse,
)
from services import analysis_service
from utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", summary="Start the analysis pipeline for an uploaded dataset")
def start_analysis(request: AnalyzeRequest) -> dict[str, Any]:
    """Run every pipeline stage and return the full analysis payload.

    The analysis intelligence is mocked; this endpoint currently exercises
    orchestration, persistence and the response contract only.
    """
    record = analysis_service.start_analysis(
        analysis_id=request.analysis_id,
        problem_description=request.problem_description,
    )
    logger.info("Analysis %s started", record["analysis_id"])
    return record


@router.get("/analyses", response_model=AnalysisListResponse, summary="List recent analyses")
def list_analyses(limit: int = Query(default=10, ge=1, le=100)) -> AnalysisListResponse:
    """Return recent analyses for the dashboard 'Recent analyses' cards."""
    records = analysis_service.list_analyses(limit=limit)
    items = [AnalysisSummary(**analysis_service.to_summary(r)) for r in records]
    return AnalysisListResponse(items=items, count=len(items))


@router.get("/analysis/{analysis_id}", summary="Fetch a full analysis payload")
def get_analysis(analysis_id: str) -> dict[str, Any]:
    """Return the complete payload for an analysis.

    All seven top-level blocks are present once the pipeline has run; a record
    that has only been uploaded returns its partial payload.
    """
    return analysis_service.get_analysis(analysis_id)


@router.get("/analysis/{analysis_id}/status", summary="Pipeline progress for an analysis")
def get_status(analysis_id: str) -> dict[str, Any]:
    """Return just the pipeline stage list and run status."""
    record = analysis_service.get_analysis(analysis_id)
    return {
        "analysis_id": record["analysis_id"],
        "status": record.get("status", "unknown"),
        "pipeline": record.get("pipeline", []),
        "data_source": record.get("data_source", "mock"),
    }


@router.delete(
    "/analysis/{analysis_id}",
    response_model=MessageResponse,
    summary="Delete an analysis",
)
def delete_analysis(analysis_id: str) -> MessageResponse:
    """Remove a stored analysis."""
    if not analysis_service.delete_analysis(analysis_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found.",
        )
    return MessageResponse(message="Analysis deleted.", analysis_id=analysis_id)


@router.get(
    "/analysis/{analysis_id}/report/download",
    response_class=PlainTextResponse,
    summary="Download the analysis report as Markdown",
)
def download_report(analysis_id: str) -> PlainTextResponse:
    """Return the report as a downloadable Markdown document."""
    record = analysis_service.get_analysis(analysis_id)
    report = record.get("report")
    if not report:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The report is not ready yet. Start the analysis first.",
        )

    filename = f"q-compass-report-{analysis_id}.md"
    return PlainTextResponse(
        content=report.get("markdown", ""),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
