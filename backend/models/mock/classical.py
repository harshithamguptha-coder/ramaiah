"""Mock classical-ML benchmark block.

No estimator from this catalogue is ever fitted — these are illustrative
figures, deterministic per analysis id.
"""

from __future__ import annotations

from typing import Any

from .common import MOCK_NOTE, rnd, rng_for

CLASSICAL_CATALOGUE = [
    ("Random Forest", "Ensemble", 0.912, 0.90, 2.4, "O(n · m · d · log n)"),
    ("XGBoost", "Gradient Boosting", 0.925, 0.915, 1.8, "O(n · d · K · log n)"),
    ("Logistic Regression", "Linear", 0.848, 0.836, 0.2, "O(n · d)"),
    ("Support Vector Machine", "Kernel", 0.884, 0.871, 18.6, "O(n² · d) – O(n³ · d)"),
    ("Neural Network (MLP)", "Deep Learning", 0.905, 0.893, 11.2, "O(n · d · H · E)"),
    ("Gradient Boosting (LightGBM)", "Boosting", 0.931, 0.922, 1.1, "O(n · d · K)"),
]


def build_classical_block(
    dataset: dict[str, Any], problem: dict[str, Any], seed: str
) -> dict[str, Any]:
    """Build the classical candidate list, baseline and resource estimate."""
    rng = rng_for(f"classical::{seed}")
    rows = dataset.get("rows") or 5000
    columns = dataset.get("column_count") or 20
    size_mb = rnd(max(0.4, (rows * columns) / 25000))

    candidates = [
        {
            "name": name,
            "family": family,
            "accuracy": rnd(acc + rng.uniform(-0.012, 0.012), 3),
            "f1_score": rnd(f1 + rng.uniform(-0.012, 0.012), 3),
            "training_time_sec": rnd(train_time * rng.uniform(0.85, 1.2)),
            "complexity": complexity,
            "suitable": True,
            "notes": f"Placeholder benchmark for {family.lower()} on this dataset shape.",
        }
        for name, family, acc, f1, train_time, complexity in CLASSICAL_CATALOGUE
    ]
    candidates.sort(key=lambda c: c["accuracy"], reverse=True)
    best, baseline = candidates[0], candidates[2]

    size_label = (
        "Small (<10 MB)" if size_mb < 10
        else "Medium (10–100 MB)" if size_mb < 100
        else "Large (>100 MB)"
    )

    return {
        "dataset_size": {
            "rows": rows, "columns": columns, "size_mb": size_mb, "label": size_label,
        },
        "candidates": candidates,
        "baseline_model": {
            "name": baseline["name"],
            "accuracy": baseline["accuracy"],
            "f1_score": baseline["f1_score"],
            "training_time_sec": baseline["training_time_sec"],
            "role": "Reference point every other model must beat.",
        },
        "best_model": {
            "name": best["name"],
            "accuracy": best["accuracy"],
            "f1_score": best["f1_score"],
            "training_time_sec": best["training_time_sec"],
        },
        "estimated_complexity": {
            "time": best["complexity"],
            "space": "O(n · d)",
            "summary": "Tractable on commodity CPU hardware for this dataset size.",
        },
        "resource_requirements": {
            "cpu_cores": 4, "memory_gb": 8, "gpu_required": False,
            "expected_runtime": "< 5 minutes",
            "notes": "No GPU is expected to be necessary at this data scale.",
        },
        "summary": (
            f"Classical baselines are expected to reach roughly "
            f"{baseline['accuracy'] * 100:.1f}–{best['accuracy'] * 100:.1f}% accuracy within minutes."
        ),
        "is_mock": True,
        "note": MOCK_NOTE,
    }
