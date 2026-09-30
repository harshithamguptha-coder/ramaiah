"""Cross-stage decision invariants.

The analytical quantum-suitability scorer was replaced by a real QAOA experiment
run on a local Qiskit Aer simulator, so the tests that pinned its factor weights
and encoding rules no longer describe the engine and have been removed.

What remains pins the invariants that must hold regardless of which quantum
engine produced the block: reproducibility of the decision, honesty about what
was actually measured, and bounded recommendation confidence.
"""

from __future__ import annotations

import math

from services import comparison_service, quantum_service, recommendation_service


def _case(d: int, rows: int = 200, task: str = "classification", opt_hits: int = 0, **overrides):
    """Build a (dataset, problem) pair that agrees on d and rows."""
    return _dataset(d, rows, **overrides), _problem(task, d, rows, opt_hits)


def _dataset(d: int, rows: int = 200, **overrides) -> dict:
    base = {
        "rows": rows,
        "column_count": d + 1,
        "target_column": "label",
        "numerical_columns": [f"f{i}" for i in range(d)],
        "categorical_columns": [],
        "id_like_features": [],
        "high_cardinality_features": [],
        "feature_cardinality": {f"f{i}": rows for i in range(d)},
        "missing_percent": 0.0,
        "feature_count": d,
    }
    base.update(overrides)
    return base


def _problem(task: str = "classification", d: int = 10, rows: int = 200, opt_hits: int = 0) -> dict:
    return {
        "problem_type": task,
        # The QAOA stage reads the display label, so both spellings are provided.
        "task_type": "Classification" if task == "classification" else task,
        "characteristics": {"features": d, "rows": rows},
        "detection": {"keyword_scores": {"optimization": opt_hits}},
    }


# ---------------------------------------------------------------------------
# Comparison + recommendation invariants
# ---------------------------------------------------------------------------


def test_criterion_weights_sum_to_one():
    assert math.isclose(sum(comparison_service.CRITERION_WEIGHTS.values()), 1.0, abs_tol=1e-9)


def test_quantum_never_claims_a_measured_accuracy():
    dataset, problem = _case(10)
    quantum = quantum_service.run(dataset, problem, "an_x")
    comparison = comparison_service.run(
        {"status": "skipped", "task": "classification", "candidates": []}, quantum, dataset
    )
    row = next(c for c in comparison["criteria"] if c["criterion"] == "Accuracy / Precision")
    assert row["quantum"]["value"] == "Not measured"
    assert comparison["approaches"]["quantum"]["measured_performance"] is None


def test_quantum_block_never_claims_hardware_execution():
    quantum = quantum_service.run(*_case(10), analysis_id="an_x")
    # No stored file was supplied, so no circuit could be built. The block has to
    # report that honestly instead of implying anything ran, and the resources it
    # advertises must be the local simulator - never a quantum device.
    assert quantum["execution"]["status"] == "not_run"
    assert quantum["quantum_analysis_real"] is False
    assert quantum["feasibility"] == "Not executable with current input"
    assert quantum["confidence"] == 0.0
    resources = quantum["estimated_resources"]
    assert resources["provider"] == "Qiskit Aer local simulator"
    assert resources["expected_queue_time"] == "None (local)"


def test_quantum_ai_is_never_recommended_for_a_weak_suitability_score():
    dataset, problem = _case(8, rows=60)
    quantum = quantum_service.run(dataset, problem, "an_x")
    comparison = comparison_service.run(
        {"status": "completed", "task": "classification", "candidates": [],
         "best_model": {"name": "Logistic Regression", "primary_score": 0.9,
                        "primary_metric": "f1_score", "accuracy": 0.9},
         "primary_metric": "f1_score", "dataset_size": {}},
        quantum,
        dataset,
    )
    recommendation = recommendation_service.run(
        comparison,
        {"status": "completed", "best_model": {"name": "Logistic Regression",
                                               "primary_score": 0.9, "primary_metric": "f1_score"},
         "primary_metric": "f1_score", "task": "classification"},
        quantum,
        problem,
        dataset,
    )
    assert recommendation["approach_key"] != "quantum"


def test_recommendation_confidence_stays_bounded():
    quantum = quantum_service.run(*_case(12), analysis_id="an_x")
    for quality in (None, 0.0, 0.55, 0.95):
        classical = {
            "status": "completed" if quality is not None else "skipped",
            "task": "classification",
            "primary_metric": "f1_score",
            "best_model": {"name": "LR", "primary_score": quality, "primary_metric": "f1_score"},
        }
        dataset, problem = _case(12)
        comparison = comparison_service.run(classical, quantum, dataset)
        recommendation = recommendation_service.run(
            comparison, classical, quantum, problem, dataset
        )
        assert 0.25 <= recommendation["confidence"] <= 0.95
        assert recommendation["approach"] == recommendation["recommended_approach"]
