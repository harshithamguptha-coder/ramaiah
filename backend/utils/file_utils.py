"""Upload validation and safe file-name handling."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

from fastapi import HTTPException, status

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    """Return a safe, collision-resistant file name that keeps the original stem.

    Guards against path traversal (``../../etc/passwd``) and reserved Windows
    characters before the name is ever joined onto a directory.
    """
    raw = Path(filename or "dataset").name
    cleaned = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    cleaned = _UNSAFE_CHARS.sub("_", cleaned).strip("._") or "dataset"

    stem, dot, ext = cleaned.rpartition(".")
    if not dot:
        stem, ext = cleaned, ""
    stem = stem[:80] or "dataset"
    return f"{stem}{('.' + ext) if ext else ''}"


def validate_extension(filename: str, allowed: tuple[str, ...]) -> str:
    """Ensure the file has an allowed extension; return it lowercased."""
    ext = Path(filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{ext or 'unknown'}'. "
                f"Allowed types: {', '.join(allowed)}"
            ),
        )
    return ext


def validate_size(size_bytes: int, max_bytes: int) -> None:
    """Reject uploads larger than the configured limit."""
    if size_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit.",
        )


def ensure_directory(path: str) -> Path:
    """Create ``path`` if needed and return it as a ``Path``."""
    directory = Path(os.path.abspath(path))
    directory.mkdir(parents=True, exist_ok=True)
    return directory
