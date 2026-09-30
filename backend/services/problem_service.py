"""Stage 2b — problem characterization.

Turns "a file plus, optionally, a sentence" into a defensible ML problem type
and the numeric characteristics the quantum scorer consumes.

How the task type is decided
----------------------------
Two independent signals are combined:

1. **Structural evidence** (strong). A target column with few distinct values is
   a classification label; a continuous, high-cardinality target is a regression
   target; no target at all leaves the choice open.
2. **Textual evidence** (weak, advisory). Keyword hits in the problem statement
   disambiguate, and are authoritative *only* for an optimisation framing, which
   has no structural signature at all.

This ordering is deliberate: a user writing "regression" in the prompt must not
turn a 2-class label column into a regression task.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np

from config import settings
from utils.errors import InvalidProblemDescriptionError
from utils.logging_config import get_logger
from utils.profiling import (
    CLASSIFICATION_HINTS,
    CLUSTERING_HINTS,
    OPTIMIZATION_HINTS,
    REGRESSION_HINTS,
    column_kind,
)

logger = get_logger(__name__)

#: Low-level taxonomy required by the API contract.
PROBLEM_TYPES = ("classification", "regression", "clustering", "optimization", "unknown")

TASK_LABELS = {
    "classification": "Classification",
    "regression": "Regression",
    "clustering": "Clustering",
    "optimization": "Optimization",
    "unknown": "Unknown",
}

MAX_DESCRIPTION_LENGTH = 2000


def clean_description(description: str | None) -> str:
    """Validate and normalise the user-supplied problem statement.

    Rejects non-text and over-long input rather than silently truncating an
    analysis-critical instruction.
    """
    if description is None:
        return ""
    if not isinstance(description, str):
        raise InvalidProblemDescriptionError("The problem description must be text.")
    text = description.strip()
    if len(text) > MAX_DESCRIPTION_LENGTH:
        raise InvalidProblemDescriptionError(
            f"The problem description is too long ({len(text)} characters). "
            f"The limit is {MAX_DESCRIPTION_LENGTH} characters.",
            details={"length": len(text), "limit": MAX_DESCRIPTION_LENGTH},
        )
    # Collapse control characters that would break report/UI rendering.
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)


def keyword_hits(text: str, hints: tuple[str, ...]) -> list[str]:
    """Return the hints that appear in ``text``."""
    return [h for h in hints if h in text]


def keyword_score(lowered: str) -> dict[str, int]:
    """Count optimisation / classification / regression / clustering cues."""
    return {
        "classification": len(keyword_hits(lowered, CLASSIFICATION_HINTS)),
        "regression": len(keyword_hits(lowered, REGRESSION_HINTS)),
        "clustering": len(keyword_hits(lowered, CLUSTERING_HINTS)),
        "optimization": len(keyword_hits(lowered, OPTIMIZATION_HINTS)),
    }


def detected_keywords(lowered: str) -> list[str]:
    """Every hint that actually fired, for display in the UI."""
    groups = (OPTIMIZATION_HINTS, CLASSIFICATION_HINTS, REGRESSION_HINTS, CLUSTERING_HINTS)
    return [h for group in groups for h in group if h in lowered][:10]


def _imbalance(series: Any) -> dict[str, Any] | None:
    """Class-balance statistics for a candidate label target."""
    if series is None or not hasattr(series, "value_counts"):
        return None
    counts = series.value_counts(dropna=True)
    if counts.empty or len(counts) < 2:
        return None
    total = float(counts.sum())
    majority = float(counts.iloc[0])
    minority = float(counts.iloc[-1])
    ratio = (majority / minority) if minority > 0 else float("inf")
    return {
        "majority_class_share": round(majority / total, 4),
        "majority_class": str(counts.index[0]),
        "minority_class": str(counts.index[-1]),
        "imbalance_ratio": round(ratio, 2) if np.isfinite(ratio) else None,
        "severity": "severe" if ratio >= 10 else "moderate" if ratio >= 3 else "balanced",
    }


def _sparsity(frame: Any, feature_columns: list[str]) -> dict[str, Any]:
    """Share of cells that are zero (numeric) or empty (categorical).

    Sparsity matters for quantum encoding because sparse one-hot / binary
    vectors are exactly what a qubit register handles poorly.
    """
    empty = {"sparsity": None, "computed": False, "note": "No features to measure."}
    if frame is None or frame.empty or not feature_columns:
        return empty
    sample = frame[feature_columns]
    total = int(sample.size)
    if total == 0:
        return empty
    if column_kind(sample[feature_columns[0]]) == "numerical":
        zeros = int((sample.select_dtypes("number") == 0).sum().sum())
        note = "Share of numeric cells equal to zero."
    else:
        zeros = int(sample.isna().sum().sum())
        note = "Share of categorical cells that are empty."
    return {"sparsity": round(zeros / total, 4), "computed": True, "note": note}


def _redundancy(frame: Any, feature_columns: list[str]) -> dict[str, Any]:
    """Count near-duplicate numerical features via |Pearson r| >= threshold.

    Redundant features inflate the apparent dimensionality without adding
    information, so a high count is a genuine argument *against* naively
    encoding everything into a qubit register.
    """
    base = {
        "method": "pearson correlation",
        "threshold": settings.analysis_correlation_threshold,
        "features_considered": 0,
        "redundant_pairs": None,
        "redundant_fraction": None,
        "computed": False,
    }
    if frame is None or frame.empty:
        return base
    numeric = [c for c in feature_columns if column_kind(frame[c]) == "numerical"]
    if len(numeric) < 2:
        return base
    capped = numeric[: settings.analysis_max_corr_features]
    corr = frame[capped].corr(numeric_only=True).abs()
    if corr.empty:
        return base
    # `.copy()` is required: pandas 3 hands back a read-only view here.
    values = corr.to_numpy().copy()
    np.fill_diagonal(values, 0.0)
    pairs = int(np.sum(np.triu(values, k=1) >= settings.analysis_correlation_threshold))
    total_pairs = len(capped) * (len(capped) - 1) / 2
    return {
        **base,
        "features_considered": len(capped),
        "redundant_pairs": pairs,
        "redundant_fraction": round(pairs / total_pairs, 4) if total_pairs else 0.0,
        "computed": True,
    }


def decide_task_type(
    lowered: str,
    scores: dict[str, int],
    structural: str,
) -> tuple[str, float, list[str]]:
    """Combine structural and textual evidence into ``(type, confidence, signals)``.

    Returns a value from :data:`PROBLEM_TYPES` plus the human-readable evidence
    trail that ends up in ``problem.detection.signals``.
    """
    signals: list[str] = []
    best_text = max(scores, key=lambda k: scores[k]) if scores else "unknown"
    text_hits = scores.get(best_text, 0)

    # 1. An explicit optimisation framing has no structural signature, so the
    #    text is authoritative for it. Two hits are required so a passing
    #    mention of "search" cannot hijack a plain prediction task.
    if scores.get("optimization", 0) >= 2:
        count = scores["optimization"]
        signals.append(
            f"Problem statement contains {count} optimisation/search terms "
            "(optimise, scheduling, routing, subset selection, ...)."
        )
        return "optimization", min(0.9, 0.55 + 0.1 * count), signals

    # 2. Otherwise trust the structure: a resolved target is decisive.
    if structural in ("classification", "regression"):
        detail = (
            "few distinct values, so this is a label (classification)."
            if structural == "classification"
            else "a continuous, high-cardinality column, so this is a numeric target "
            "(regression)."
        )
        signals.append("Target column resolved from the data: " + detail)
        agrees = scores.get(structural, 0) > 0
        confidence = (0.91 if agrees else 0.78) if structural == "classification" else (
            0.9 if agrees else 0.75
        )
        return structural, confidence, signals

    # 3. No usable target: the text decides between clustering and unknown.
    if text_hits and scores.get("clustering", 0) >= max(1, scores.get("classification", 0)):
        signals.append(
            "No target column was found and the problem statement describes "
            "grouping/segmentation, so this is treated as clustering."
        )
        return "clustering", min(0.8, 0.5 + 0.1 * scores["clustering"]), signals

    if text_hits and best_text in ("regression", "classification") and text_hits >= 2:
        # The statement names a supervised task, but no target column exists to
        # train against. Report the stated task so the user can see what the
        # engine understood, while making clear that no model was trained.
        signals.append(
            "No target column was detected, so no model can be trained, but the "
            f"problem statement clearly describes {best_text} "
            f"(keyword score {text_hits}). Specify the target column to evaluate it."
        )
        return best_text, min(0.6, 0.3 + 0.1 * text_hits), signals

    if text_hits:
        signals.append(
            "No target column was found; the problem statement leans "
            f"{best_text} (keyword score {text_hits})."
        )
        return "unknown", min(0.6, 0.35 + 0.1 * text_hits), signals

    signals.append(
        "Neither the data structure nor the problem statement identifies a task type."
    )
    return "unknown", 0.3, signals


def build_problem(
    description: str | None,
    dataset: dict[str, Any],
    frame: Any | None = None,
) -> dict[str, Any]:
    """Return the ``problem`` block for an analysis.

    ``frame`` is the cached DataFrame. It is optional: when it is missing (for
    example the file could not be parsed) the block is still produced from the
    dataset profile alone, with the affected characteristics reported as
    unavailable rather than invented.
    """
    text = clean_description(description)
    lowered = text.lower()
    scores = keyword_score(lowered)

    target = dataset.get("target_column")
    structural = dataset.get("problem_type") or "unknown"
    if structural not in ("classification", "regression"):
        structural = "unknown"

    problem_type, confidence, signals = decide_task_type(lowered, scores, structural)

    rows = int(dataset.get("rows") or 0)
    columns = dataset.get("column_names") or []
    features = [c for c in columns if c != target] if columns else []
    d = len(features) if features else int(dataset.get("feature_count") or 0)

    has_frame = frame is not None
    target_series = (
        frame[target] if (has_frame and target and target in frame.columns) else None
    )
    imbalance = _imbalance(target_series)
    sparsity = (
        _sparsity(frame, features)
        if has_frame
        else {"sparsity": None, "computed": False, "note": "Dataset could not be parsed."}
    )
    redundancy = (
        _redundancy(frame, features)
        if has_frame
        else {
            "method": "pearson correlation",
            "threshold": settings.analysis_correlation_threshold,
            "features_considered": 0,
            "redundant_pairs": None,
            "redundant_fraction": None,
            "computed": False,
        }
    )

    n_classes = dataset.get("class_count") if problem_type == "classification" else None
    if problem_type == "classification" and n_classes is None and target_series is not None:
        n_classes = int(target_series.nunique())

    paradigm = (
        "Supervised Learning"
        if problem_type in ("classification", "regression")
        else "Unsupervised / Unspecified"
    )

    if problem_type == "optimization":
        summary = (
            "Optimisation / search problem described in the problem statement "
            f"({rows:,} rows, {d} features available as input to the search)."
        )
    else:
        summary = (
            f"{TASK_LABELS[problem_type]} over tabular data with {rows:,} rows and {d} features"
            + (f", target column '{target}'." if target else " and no detected target column.")
        )

    return {
        # --- existing frontend contract (names unchanged) ---
        "description": text or "No problem description provided.",
        "task_type": TASK_LABELS[problem_type],
        "task_type_confidence": round(confidence, 2),
        "learning_paradigm": paradigm,
        "target_column": target,
        "keywords": detected_keywords(lowered),
        "detected_modalities": ["Tabular"],
        "summary": summary,
        "is_mock": False,
        "note": (
            "Task type inferred from the dataset structure, with the problem "
            "statement used to disambiguate and to detect an optimisation framing."
        ),
        # --- extended characterization ---
        "problem_type": problem_type,
        "characteristics": {
            "rows": rows,
            "features": d,
            "feature_dimensionality": d,
            "feature_to_sample_ratio": round(d / rows, 4) if rows else None,
            "num_classes": n_classes,
            "class_imbalance": imbalance,
            "sparsity": sparsity.get("sparsity"),
            "sparsity_detail": sparsity,
            "redundancy": redundancy,
            "estimated_search_space": 2**d if d <= 512 else None,
            "estimated_search_space_log2": float(d),
            "memory_footprint_mb": dataset.get("memory_footprint_mb"),
            "size_label": dataset.get("size_label"),
        },
        "detection": {
            "method": "target-column structure + keyword disambiguation",
            "structural_evidence": structural,
            "keyword_scores": scores,
            "signals": signals,
            "description_provided": bool(text),
        },
        "warnings": _problem_warnings(rows, d, problem_type, imbalance, target),
    }


def _problem_warnings(
    rows: int,
    d: int,
    problem_type: str,
    imbalance: dict[str, Any] | None,
    target: str | None,
) -> list[str]:
    out: list[str] = []
    if rows == 0:
        out.append("No usable rows were read from the dataset.")
    if not target:
        out.append("No target column was detected, so supervised baselines are skipped.")
    if rows and rows < 30:
        out.append(f"Only {rows} rows are available; model scores on this sample will be noisy.")
    if imbalance and imbalance.get("severity") == "severe":
        share = round((imbalance.get("majority_class_share") or 0) * 100)
        out.append(f"Severe class imbalance: the majority class is {share}% of the target.")
    if d > rows:
        out.append(
            f"More features ({d}) than rows ({rows}) - the problem is high-dimensional "
            "and prone to overfitting."
        )
    if problem_type == "optimization":
        out.append(
            "The problem statement describes an optimisation task; a predictive "
            "baseline may not be the right yardstick for it."
        )
    return out
