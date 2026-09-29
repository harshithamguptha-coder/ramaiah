"""Comparison stage.

Seam for a real scoring model: it only ever consumes the classical and quantum
blocks, so the weighting strategy can change without touching anything else.
"""

from __future__ import annotations

from typing import Any

from models.mock import build_comparison_block


def run(
    classical: dict[str, Any],
    quantum: dict[str, Any],
    dataset: dict[str, Any],
    analysis_id: str = "",
) -> dict[str, Any]:
    """Produce the three-way comparison block."""
    return build_comparison_block(classical, quantum, dataset)
