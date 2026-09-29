"""Recommendation stage.

Seam for a real decision engine (learned ranker, rules engine, LLM-assisted
explanation). Currently a deterministic placeholder derived from the mock
comparison scores.
"""

from __future__ import annotations

from typing import Any

from models.mock import build_recommendation_block


def run(
    comparison: dict[str, Any],
    classical: dict[str, Any],
    quantum: dict[str, Any],
    problem: dict[str, Any],
    dataset: dict[str, Any],
    analysis_id: str = "",
) -> dict[str, Any]:
    """Produce the recommendation block."""
    return build_recommendation_block(comparison, classical, quantum, problem, dataset)
