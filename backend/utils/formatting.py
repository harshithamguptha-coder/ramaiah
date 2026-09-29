"""Human-readable formatting helpers used when building mock payloads."""

from __future__ import annotations


def human_file_size(num_bytes: float) -> str:
    """Format a byte count as e.g. ``1.4 MB``."""
    if num_bytes is None:
        return "—"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024.0 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"


def percentage(value: float, digits: int = 1) -> str:
    """Format a 0-100 ratio as a percentage string."""
    return f"{value:.{digits}f}%"


def seconds(value: float) -> str:
    """Format a duration in seconds, switching units for large values."""
    if value is None:
        return "—"
    if value < 1:
        return f"{value * 1000:.0f} ms"
    if value < 60:
        return f"{value:.1f} sec"
    return f"{value / 60:.1f} min"
