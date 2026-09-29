"""Mock dataset profile and problem-classification blocks."""

from __future__ import annotations

from typing import Any

from utils.formatting import human_file_size
from utils.ids import utc_now_iso

from .common import PROBLEM_KEYWORDS, pick_task_type, rnd, rng_for


def build_dataset_block(metadata: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Merge upload metadata with the structural profile into the dataset block."""
    size = metadata.get("file_size_bytes", 0)

    return {
        "file_id": metadata.get("file_id"),
        "file_name": metadata.get("file_name"),
        "file_size_bytes": size,
        "file_size_display": human_file_size(size),
        "file_type": metadata.get("file_type"),
        "uploaded_at": metadata.get("uploaded_at", utc_now_iso()),
        "rows": profile.get("rows"),
        "column_count": len(profile.get("columns") or []),
        "column_names": profile.get("columns") or [],
        "numerical_features": profile.get("numerical_features"),
        "categorical_features": profile.get("categorical_features"),
        "missing_values": profile.get("missing_values"),
        "missing_percent": profile.get("missing_percent"),
        "target_column": profile.get("target_column"),
        "feature_names": profile.get("feature_names", [])[:12],
        "feature_count": len(profile.get("feature_names", [])),
        "memory_footprint_mb": rnd((size or 0) / (1024 * 1024)) if size else None,
        "profile_method": profile.get("profile_method"),
        "profiled": bool(profile.get("rows")),
        "is_mock": False,
        "note": (
            "Shape information read structurally from your file. Distributions, "
            "correlations and label statistics are not computed yet."
        ),
    }


def build_problem_block(description: str, dataset: dict[str, Any]) -> dict[str, Any]:
    """Mock problem classification block."""
    text = (description or "").strip()
    task_type, confidence = pick_task_type(text)
    rng = rng_for(str(dataset.get("file_id") or task_type))

    keywords = [k for k in PROBLEM_KEYWORDS if k in text.lower()] or rng.sample(PROBLEM_KEYWORDS, 4)
    target = dataset.get("target_column")

    return {
        "description": text or "No problem description provided.",
        "task_type": task_type,
        "task_type_confidence": confidence,
        "learning_paradigm": "Supervised Learning" if target else "Unsupervised / Unspecified",
        "target_column": target,
        "keywords": keywords,
        "detected_modalities": ["Tabular"],
        "summary": (
            f"Classified as {task_type} over tabular data"
            + (f" with target column '{target}'." if target else " (no target column detected).")
        ),
        "is_mock": True,
        "note": "Task-type inference is a keyword heuristic placeholder.",
    }
