"""Lightweight, structural dataset profiling.

IMPORTANT — this is intentionally *not* analysis. It reads just enough of a
file to describe its shape (row/column counts, dtypes, missing cells, a
plausible target column) so the prototype demonstrates against real input.
All predictive/quantum intelligence is mocked elsewhere.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

# Only the first N rows are scanned; large files get estimated metadata.
SAMPLE_ROWS = 500

_TARGET_HINTS = (
    "target", "label", "class", "y", "outcome", "result", "status", "churn",
    "is_", "has_", "fraud", "default", "prediction", "dependent", "response",
)


def looks_numeric(values: list[str]) -> bool:
    """Return True when most non-empty sample values parse as numbers."""
    filled = [v for v in values if v not in ("", None)]
    if len(filled) < max(2, len(values) * 0.5):
        return False
    numeric = 0
    for value in filled[:200]:
        try:
            float(re.sub(r"[,%\s$]", "", str(value)))
            numeric += 1
        except (TypeError, ValueError):
            continue
    return numeric / len(filled[:200]) >= 0.8


def guess_target_column(columns: list[str]) -> str | None:
    """Pick the most likely label column using naming heuristics."""
    if not columns:
        return None
    lowered = [(col, col.lower().strip()) for col in columns]
    for column, low in lowered:
        if low in ("target", "label", "class", "y", "outcome", "result"):
            return column
    for column, low in lowered:
        if any(low.startswith(hint) for hint in _TARGET_HINTS):
            return column
    for column, low in reversed(lowered):
        if low.startswith("is_") or low.startswith("has_"):
            return column
    return None


def _profile_csv(content: bytes) -> dict[str, Any]:
    """Read header + sampled rows from a CSV to describe its shape."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, [])
    columns = [c.strip() or f"column_{i + 1}" for i, c in enumerate(header)]

    sample: list[list[str]] = []
    total_rows = 0
    missing = 0
    for index, row in enumerate(reader):
        total_rows += 1
        if index < SAMPLE_ROWS:
            sample.append(row)
            for cell in row:
                if cell.strip() == "":
                    missing += 1

    columns_data: dict[str, list[str]] = {c: [] for c in columns}
    for row in sample:
        for i, cell in enumerate(row[: len(columns)]):
            columns_data[columns[i]].append(cell.strip())

    target = guess_target_column(columns)
    numeric = [c for c, vals in columns_data.items() if looks_numeric(vals)]
    categorical = [c for c in columns if c not in numeric]
    missing_ratio = (missing / total_rows) if total_rows else 0.0

    return {
        "rows": total_rows,
        "columns": columns,
        "numerical_features": len(numeric),
        "categorical_features": len(categorical),
        "feature_names": [c for c in columns if c != target],
        "missing_values": int(missing_ratio * total_rows * len(columns)),
        "missing_percent": round(missing_ratio * 100, 2),
        "target_column": target,
        "profile_method": "structural-scan (CSV sample)",
    }


def _profile_json(content: bytes) -> dict[str, Any]:
    """Support both a top-level JSON array/object and JSON Lines."""
    text = content.decode("utf-8-sig", errors="replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = [
            json.loads(line) for line in text.splitlines()[:SAMPLE_ROWS] if line.strip()
        ]

    if isinstance(payload, dict):
        records = [payload]
    elif isinstance(payload, list):
        records = payload
    else:
        records = [{"value": payload}]

    keys: list[str] = []
    for record in records[:SAMPLE_ROWS]:
        if isinstance(record, dict):
            for key in record:
                if key not in keys:
                    keys.append(key)

    sample_len = max(1, min(len(records), SAMPLE_ROWS))
    missing = sum(
        1
        for record in records[:SAMPLE_ROWS]
        if isinstance(record, dict)
        for key in keys
        if record.get(key) in (None, "")
    )
    numeric = [
        key
        for key in keys
        if looks_numeric(
            [str(rec.get(key, "")) for rec in records[:SAMPLE_ROWS] if isinstance(rec, dict)]
        )
    ]
    target = guess_target_column(keys)

    return {
        "rows": len(records),
        "columns": len(keys),
        "columns_data": keys,
        "numerical_features": len(numeric),
        "categorical_features": len(keys) - len(numeric),
        "feature_names": [key for key in keys if key != target],
        "missing_values": int(missing / sample_len * max(1, len(keys))),
        "missing_percent": round(missing / sample_len / max(1, len(keys)) * 100, 2),
        "target_column": target,
        "profile_method": "structural-scan (JSON sample)",
    }


def _profile_xlsx(file_size: int) -> dict[str, Any]:
    """XLSX is a zip container and needs an extra reader dependency.

    The prototype deliberately avoids pulling in a spreadsheet engine, so only
    file-level facts are reported and the shape is flagged as not-parsed.
    """
    return {
        "rows": None,
        "columns": None,
        "numerical_features": None,
        "categorical_features": None,
        "feature_names": [],
        "missing_values": None,
        "missing_percent": None,
        "target_column": None,
        "profile_method": "not-parsed (XLSX reader not enabled in prototype)",
        "estimated_from_size": file_size,
    }


def profile_dataset(content: bytes, extension: str, file_size: int) -> dict[str, Any]:
    """Return a structural profile for an uploaded dataset.

    Never raises: a malformed file degrades to an empty, flagged profile so the
    upload flow itself still succeeds.
    """
    try:
        if extension == ".csv":
            profile = _profile_csv(content)
        elif extension == ".json":
            profile = _profile_json(content)
        elif extension == ".xlsx":
            profile = _profile_xlsx(file_size)
        else:
            raise ValueError(f"Unsupported extension: {extension}")
    except Exception as exc:  # noqa: BLE001 - profiling must never break upload
        profile = {
            "rows": None,
            "columns": None,
            "numerical_features": None,
            "categorical_features": None,
            "feature_names": [],
            "missing_values": None,
            "missing_percent": None,
            "target_column": None,
            "profile_method": f"failed ({type(exc).__name__})",
        }

    profile["columns_data"] = profile.get("columns_data") or profile.get("columns") or []
    return profile
