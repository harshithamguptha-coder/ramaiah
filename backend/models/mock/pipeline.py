"""Pipeline stage definitions shared by the API and the frontend stepper."""

from __future__ import annotations

from typing import Any

PIPELINE_STAGES: list[dict[str, Any]] = [
    {
        "key": "upload",
        "label": "Dataset uploaded",
        "description": "File received, validated and stored.",
        "route": "/upload",
    },
    {
        "key": "profiling",
        "label": "Dataset profiling",
        "description": "Shape, feature types and missing values inspected.",
        "route": "/analysis",
    },
    {
        "key": "classical",
        "label": "Classical analysis",
        "description": "Classical algorithm candidates and baselines.",
        "route": "/classical",
    },
    {
        "key": "quantum",
        "label": "Quantum analysis",
        "description": "Quantum suitability and candidate circuits.",
        "route": "/quantum",
    },
    {
        "key": "comparison",
        "label": "Comparison",
        "description": "Weighted Classical vs Quantum vs Hybrid matrix.",
        "route": "/comparison",
    },
    {
        "key": "recommendation",
        "label": "Recommendation",
        "description": "Recommended approach with reasoning.",
        "route": "/recommendation",
    },
    {
        "key": "report",
        "label": "Report generation",
        "description": "Consolidated report assembled for download.",
        "route": "/report",
    },
]


def build_pipeline(completed_through: str | None = None) -> list[dict[str, Any]]:
    """Return the pipeline with per-stage status.

    ``completed_through`` is the ``key`` of the last stage that has finished;
    that stage and everything before it are ``completed``, the rest are
    ``pending``. Pass ``None`` for a pipeline that has not started.
    """
    order = [stage["key"] for stage in PIPELINE_STAGES]
    cutoff = order.index(completed_through) if completed_through in order else -1

    return [
        {
            **stage,
            "status": "completed" if index <= cutoff else "pending",
            "order": index + 1,
        }
        for index, stage in enumerate(PIPELINE_STAGES)
    ]
