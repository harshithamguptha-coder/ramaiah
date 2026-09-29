"""Typed request/response contracts for the API.

The analysis payload is intentionally a loose ``dict``-shaped object for now.
Once real engines exist these can be promoted to strict nested models without
breaking the frontend, because the top-level keys are already fixed:
``dataset``, ``problem``, ``classical_analysis``, ``quantum_analysis``,
``comparison``, ``recommendation``, ``report``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    service: str
    version: str
    environment: str
    mode: str = Field(description="'mock' while analysis engines are placeholders")
    time: str


class DatasetMetadata(BaseModel):
    file_id: str
    file_name: str
    file_size_bytes: int
    file_type: str
    uploaded_at: str
    stored_path: str | None = None


class UploadResponse(BaseModel):
    analysis_id: str
    status: str
    message: str
    dataset: dict[str, Any]
    problem: dict[str, Any]
    pipeline: list[dict[str, Any]]
    data_source: str = "mock"


class AnalyzeRequest(BaseModel):
    analysis_id: str | None = Field(
        default=None, description="Re-analyse an existing upload. Omit to create a new run."
    )
    file_id: str | None = Field(default=None, description="Dataset to analyse.")
    problem_description: str | None = Field(
        default=None, max_length=2000, description="Optional AI problem statement."
    )
    include_mock: bool = Field(
        default=True, description="Kept for API stability; mock data is the only source now."
    )


class AnalysisSummary(BaseModel):
    analysis_id: str
    created_at: str
    file_name: str
    problem_description: str
    task_type: str
    recommended_approach: str
    confidence: float
    status: str


class AnalysisListResponse(BaseModel):
    items: list[AnalysisSummary]
    count: int


class MessageResponse(BaseModel):
    message: str
    analysis_id: str | None = None
