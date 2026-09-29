"""Classical analysis stage.

This is the seam where a real benchmark engine plugs in. Replace the body of
``run`` with model training/evaluation (scikit-learn, XGBoost, AutoML, ...);
its signature and the block it returns stay the same.
"""

from __future__ import annotations

from typing import Any

from models.mock import build_classical_block


def run(dataset: dict[str, Any], problem: dict[str, Any], analysis_id: str) -> dict[str, Any]:
    """Produce the classical analysis block for an analysis run."""
    return build_classical_block(dataset, problem, analysis_id)
