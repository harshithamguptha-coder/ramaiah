"""Identifier helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_analysis_id() -> str:
    """Return a short, URL-safe, sortable-enough analysis identifier."""
    return f"an_{uuid.uuid4().hex[:12]}"


def new_file_id() -> str:
    """Return a short identifier for an uploaded file."""
    return f"fl_{uuid.uuid4().hex[:12]}"


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
