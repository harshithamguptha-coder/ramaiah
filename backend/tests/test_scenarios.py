"""The three specified scenarios.

Each test asserts both the *outcome* and the *reasoning* that produced it, so a
change in scoring that flips a verdict without explaining itself fails the suite.
"""

from __future__ import annotations

from conftest import (
    make_high_dimensional,
    make_optimization,
    make_small_classification,
)


# ---------------------------------------------------------------------------
# Dataset 1 - small classification
# ---------------------------------------------------------------------------


def test_dataset1_small_classification_prefers_classical(analyze_csv):
    """Expected: classical is highly feasible and is what gets recommended."""
    payload = analyze_csv(
        make_small_classification().to_csv(index=False).encode(),
        description="Classify whether a customer will churn this month.",
    )
    classical = payload["classical_analysis"]
    quantum = payload["quantum_analysis"]
    recommendation = payload["recommendation"]

    # The problem was actually characterised.
    assert payload["problem"]["problem_type"] == "classification"
    assert payload["problem"]["target_column"] == "is_churned"

    # A real model was trained and it beat the trivial majority-class floor.
    assert classical["status"] == "completed"
    best = classical["best_model"]
    baseline = classical["baseline_model"]
    assert best["primary_score"] > baseline["primary_score"]
    assert best["primary_score"] >= 0.7, "a clean separable dataset should be learnable"
    assert classical["primary_metric"] == "f1_score"

    # Classical is highly feasible.
    assert payload["comparison"]["approaches"]["classical"]["feasibility"] == "High"
    assert payload["comparison"]["weighted_scores"]["classical"] > payload["comparison"][
        "weighted_scores"
    ]["quantum"]

    # And it is what is recommended - never quantum by default.
    assert recommendation["approach_key"] in ("classical", "hybrid")
    assert recommendation["approach_key"] != "quantum"
    assert "measured" in recommendation["decision_basis"] or "Gate" in recommendation["decision_basis"]


def test_dataset1_reasons_grounded_in_measurements(analyze_csv):
    """The explanation must cite the measured score, not a canned sentence."""
    payload = analyze_csv(
        make_small_classification().to_csv(index=False).encode(),
        description="Classify whether a customer will churn this month.",
    )
    recommendation = payload["recommendation"]
    best = payload["classical_analysis"]["best_model"]

    assert recommendation["reasons"], "a recommendation must explain itself"
    joined = " ".join(r["detail"] for r in recommendation["reasons"])
    assert best["name"] in joined
    assert str(payload["quantum_analysis"]["suitability_score"]) in joined
    assert recommendation["gates_evaluated"]
    assert recommendation["input_confidence"] > 0.5


# ---------------------------------------------------------------------------
# Dataset 2 - high-dimensional feature-selection problem
# ---------------------------------------------------------------------------


def test_dataset2_identifies_quantum_feature_selection(analyze_csv):
    """Expected: quantum feature selection is surfaced as a research direction."""
    payload = analyze_csv(
        make_high_dimensional().to_csv(index=False).encode(),
        description=(
            "Predict the target from a wide set of mostly noisy candidate features. "
            "The real challenge is deciding which subset of the features to keep."
        ),
    )
    quantum = payload["quantum_analysis"]
    characteristics = payload["problem"]["characteristics"]

    # A genuinely large selection space was measured.
    assert characteristics["features"] == 48
    assert characteristics["estimated_search_space_log2"] == 48.0
    assert payload["dataset"]["feature_count"] == 48

    # QAOA feature-relationship optimisation is the quantum candidate, bounded by
    # the local simulator's qubit cap rather than by the dataset width.
    assert quantum["potential_methods"] == ["QAOA"]
    assert quantum["primary_algorithm"].startswith("QAOA")
    assert 0 <= quantum["qubits_required"] <= 6

    # The reported factors are the ones the executed circuit actually measured.
    factors = {f["factor"]: f for f in quantum["suitability"]["factors"]}
    assert {"Quantum formulation", "Qubit budget", "Circuit complexity"} <= factors.keys()
    assert 0 <= quantum["suitability_score"] <= 100


def test_dataset2_does_not_claim_quantum_will_win(analyze_csv):
    """High suitability must never be presented as a predicted accuracy."""
    payload = analyze_csv(
        make_high_dimensional().to_csv(index=False).encode(),
        description="Predict the target from a wide set of noisy candidate features.",
    )
    quantum = payload["quantum_analysis"]
    comparison = payload["comparison"]

    assert quantum["execution"]["hardware_executed"] is False
    assert quantum["execution"]["mode"] == "local-qiskit-aer-simulation"
    # Simulator output is never dressed up as a quantum performance claim.
    assert any("not quantum advantage" in limit for limit in quantum["limitations"])

    accuracy_row = next(
        c for c in comparison["criteria"] if c["criterion"] == "Accuracy / Precision"
    )
    assert accuracy_row["quantum"]["value"] == "Not measured"
    assert accuracy_row["quantum"]["basis"] == "assumption"
    assert comparison["approaches"]["quantum"]["measured_performance"] is None

    # A real classical model was still trained and is the production answer.
    assert payload["classical_analysis"]["status"] == "completed"
    assert payload["recommendation"]["approach_key"] in ("classical", "hybrid")


# ---------------------------------------------------------------------------
# Dataset 3 - optimisation-style problem
# ---------------------------------------------------------------------------


def test_dataset3_detects_optimisation_and_surfaces_qaoa(analyze_csv):
    """Expected: QAOA is identified as a candidate for an optimisation task."""
    payload = analyze_csv(
        make_optimization().to_csv(index=False).encode(),
        description=(
            "Schedule the jobs across machines to minimise total cost subject to "
            "capacity constraints. This is a combinatorial optimisation and routing "
            "assignment problem."
        ),
    )
    quantum = payload["quantum_analysis"]
    problem = payload["problem"]

    assert problem["problem_type"] == "optimization"
    assert problem["task_type"] == "Optimization"
    assert problem["detection"]["structural_evidence"] == "unknown", (
        "there is no target column, so the text must be what drives the verdict"
    )
    assert "QAOA" in quantum["potential_methods"]
    assert quantum["primary_algorithm"].startswith("QAOA")

    factors = {f["factor"]: f for f in quantum["suitability"]["factors"]}
    assert factors["Quantum formulation"]["points"] > 0


def test_dataset3_skips_supervised_baseline_correctly(analyze_csv):
    """With no target column, no predictive model may be invented."""
    payload = analyze_csv(
        make_optimization().to_csv(index=False).encode(),
        description=(
            "Minimise total cost under constraints; this is a combinatorial "
            "optimisation and assignment problem."
        ),
    )
    classical = payload["classical_analysis"]
    assert classical["status"] == "skipped"
    assert classical["best_model"] is None
    assert classical["candidates"] == []
    assert "target column" in classical["summary"].lower()
