"""The scoring must be reproducible, transparent and monotonic.

These tests pin the *formula*, not the outputs: if someone changes a weight,
these fail and force the documentation to be updated too.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from config import settings
from services import comparison_service, quantum_service, recommendation_service
from services.quantum_service import (
    FACTOR_WEIGHTS,
    estimate_qubits,
    score_suitability,
)


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
        "characteristics": {"features": d, "rows": rows},
        "detection": {"keyword_scores": {"optimization": opt_hits}},
    }


# ---------------------------------------------------------------------------
# The formula
# ---------------------------------------------------------------------------


def test_weights_sum_to_one():
    assert math.isclose(sum(FACTOR_WEIGHTS.values()), 1.0, abs_tol=1e-9)
    assert len(FACTOR_WEIGHTS) == 6


def test_score_is_reproducible():
    """Same input in, same score out - no hidden randomness."""
    dataset, problem = _case(12)
    first = score_suitability(dataset, problem)
    second = score_suitability(dataset, problem)
    assert first == second


def test_raw_score_equals_the_declared_weighted_sum():
    """The published formula must actually reproduce the score."""
    dataset, problem = _case(20, rows=800)
    scored = score_suitability(dataset, problem)

    total = sum(f["contribution"] for f in scored["factors"])
    assert math.isclose(total, scored["raw_score"] / 100, abs_tol=1e-3)
    for factor in scored["factors"]:
        assert math.isclose(
            factor["normalised"] * factor["weight"], factor["contribution"], abs_tol=1e-3
        )
        assert 0.0 <= factor["normalised"] <= 1.0
        assert factor["explanation"]


def test_every_factor_contributes_and_is_explained():
    scored = score_suitability(*_case(15))
    assert {f["key"] for f in scored["factors"]} == set(FACTOR_WEIGHTS)
    assert all(f["explanation"] for f in scored["factors"])


# ---------------------------------------------------------------------------
# Monotonic behaviour - the score must track the data, not noise
# ---------------------------------------------------------------------------


def test_wider_feature_space_scores_higher_search_factor():
    narrow = {f["key"]: f for f in score_suitability(*_case(4))["factors"]}
    wide = {f["key"]: f for f in score_suitability(*_case(50))["factors"]}
    assert wide["search_space_complexity"]["normalised"] > narrow["search_space_complexity"]["normalised"]
    # ... but a wider space is harder to encode.
    assert wide["feature_dimensionality"]["normalised"] < narrow["feature_dimensionality"]["normalised"]


def test_more_rows_reduce_sample_compatibility():
    small = {f["key"]: f for f in score_suitability(*_case(10, rows=100))["factors"]}
    large = {f["key"]: f for f in score_suitability(*_case(10, rows=50_000))["factors"]}
    assert (
        large["dataset_size_compatibility"]["normalised"]
        < small["dataset_size_compatibility"]["normalised"]
    )


def test_optimisation_framing_scores_highest_optimization_factor():
    plain = {f["key"]: f for f in score_suitability(*_case(10))["factors"]}
    optim = {
        f["key"]: f
        for f in score_suitability(*_case(10, task="optimization", opt_hits=3))["factors"]
    }
    assert optim["optimization_suitability"]["normalised"] == 1.0
    assert (
        optim["optimization_suitability"]["normalised"]
        > plain["optimization_suitability"]["normalised"]
    )


def test_score_increases_when_problem_becomes_more_quantum_shaped():
    """A small optimisation problem must out-score a wide, data-heavy one."""
    small_optim = score_suitability(*_case(6, rows=100, task="optimization", opt_hits=2))
    wide_predict = score_suitability(*_case(400, rows=90_000))
    assert small_optim["suitability_score"] > wide_predict["suitability_score"]


# ---------------------------------------------------------------------------
# Hard caps
# ---------------------------------------------------------------------------


def test_cap_applies_when_the_register_exceeds_the_reference_budget():
    huge_d = settings.quantum_reference_qubits + 50
    scored = score_suitability(*_case(huge_d, rows=50, task="optimization", opt_hits=3))
    assert scored["suitability_score"] <= 25
    assert any(c["cap"] == 25 for c in scored["caps_applied"])


def test_cap_applies_for_wide_predictive_problems():
    scored = score_suitability(*_case(300, rows=10_000))
    assert scored["suitability_score"] <= 35
    assert any(c["cap"] == 35 for c in scored["caps_applied"])


def test_score_is_always_bounded():
    for d in (1, 5, 20, 64, 200, 900):
        for rows in (10, 500, 10_000, 500_000):
            for task in ("classification", "optimization", "unknown"):
                scored = score_suitability(*_case(d, rows, task, 2))
                assert 0 <= scored["suitability_score"] <= 100


# ---------------------------------------------------------------------------
# Encoding / qubits
# ---------------------------------------------------------------------------


def test_amplitude_encoding_is_not_recommended_for_wide_data():
    """It uses few qubits, but its state-prep cost makes it a bad advice."""
    encoding = estimate_qubits(_dataset(40), 40)
    assert encoding["recommended"] != "Amplitude encoding"
    assert encoding["amplitude_state_preparation_swaps"] > 0


def test_recommended_encoding_follows_the_state_preparation_rule():
    """Amplitude encoding only wins while its state prep stays trivial."""
    # d = 6 -> ceil(log2 6) = 3 qubits and only 2 swap gates of state preparation.
    small = estimate_qubits(_dataset(6), 6)
    assert small["recommended"] == "Amplitude encoding"
    assert small["recommended_qubits"] == 3
    assert small["amplitude_state_preparation_swaps"] == 2

    # d = 20 -> 32 amplitude qubits, but 20 qubits and no state prep via angle
    # encoding wins, because state preparation is no longer negligible.
    wide = estimate_qubits(_dataset(20), 20)
    assert wide["recommended"] == "Angle encoding"
    assert wide["recommended_qubits"] == 20


def test_target_column_is_excluded_from_encoding_cost():
    """A 2-level label must not make the dataset look cheap to encode."""
    dataset = _dataset(
        20,
        categorical_columns=["colour"],
        feature_cardinality={**{f"f{i}": 200 for i in range(20)}, "colour": 3, "label": 2},
    )
    encoding = estimate_qubits(dataset, 20)
    assert encoding["categorical_input_columns"] == ["colour"]
    assert encoding["one_hot_qubits"] == 3


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
    assert quantum["execution"]["hardware_executed"] is False
    assert quantum["execution"]["mode"] == "theoretical-suitability-analysis"
    assert "does NOT" in quantum["score_interpretation"]


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
