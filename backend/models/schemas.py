"""Typed request/response contracts for the API.

The analysis payload is intentionally a loose ``dict``-shaped object, because
the frontend consumes a stable set of top-level keys and adding strict nested
models would risk breaking it. Those keys are now all populated by the real
analysis engine:

===========================  =========================================
Key                         Produced by
===========================  =========================================
``dataset``                 services/dataset_service.py
``problem``                 services/problem_service.py
``classical_analysis``      services/classical_service.py
``quantum_analysis``        services/quantum_service.py
``comparison``              services/comparison_service.py
``recommendation``          services/recommendation_service.py
``report``                  services/report_service.py
``warnings``                services/analysis_service.py (flattened)
===========================  =========================================

Every block additionally carries ``is_mock: false`` so the UI can tell a measured
value from a placeholder, and ``warnings`` for anything a reader should know
before trusting the numbers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    service: str
    version: str
    environment: str
    mode: str = Field(description="'real' - the analysis engine produces measured values")
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
    data_source: str = "real"


class AnalyzeRequest(BaseModel):
    analysis_id: str | None = Field(
        default=None, description="Re-analyse an existing upload. Omit to create a new run."
    )
    file_id: str | None = Field(default=None, description="Dataset to analyse.")
    problem_description: str | None = Field(
        default=None, max_length=2000, description="Optional AI problem statement."
    )
    target_column: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Target/label column to use. Omit to auto-detect from the column name. "
            "A name that is not present in the dataset is ignored with a warning."
        ),
    )
    include_mock: bool = Field(
        default=False,
        description="Retained for API stability; the engine no longer produces mock data.",
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
