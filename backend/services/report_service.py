"""Report stage: assembles the final document and the Markdown download."""

from __future__ import annotations

from typing import Any

from models.mock import build_report_block


def run(payload: dict[str, Any]) -> dict[str, Any]:
    """Produce the report block from a complete analysis payload."""
    return build_report_block(payload)
