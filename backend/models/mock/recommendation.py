"""Mock recommendation block.

The recommendation is derived deterministically from the comparison scores so
the pages stay internally consistent, but it is NOT produced by any
recommendation model — it is a lookup over placeholder scores.
"""

from __future__ import annotations

from typing import Any

from .common import APPROACH_LABELS, rnd

_DISCLAIMER = (
    "This recommendation is produced from placeholder scores in the Q-Compass "
    "prototype. It is not the output of a real quantum analysis engine and must "
    "not be used to justify a production decision."
)

_BENEFITS = {
    "hybrid": [
        "Keeps the accuracy and reliability of a proven classical model.",
        "Lets a quantum sub-routine be evaluated in isolation, with a safe fallback.",
        "Builds quantum expertise before hardware catches up with the algorithm.",
    ],
    "classical": [
        "Fastest path to production; no new infrastructure required.",
        "Best accuracy-to-effort ratio for tabular problems today.",
        "Fully reproducible, debuggable and well-understood operationally.",
    ],
    "quantum": [
        "Explores the problem class where future hardware may provide an advantage.",
        "Builds an in-house quantum capability ahead of the technology curve.",
    ],
}

_LIMITATIONS = {
    "hybrid": [
        "Two toolchains to maintain and a larger integration surface.",
        "The quantum sub-routine may add cost without measurable benefit yet.",
        "End-to-end latency is higher than a purely classical pipeline.",
    ],
    "classical": [
        "May hit a performance ceiling that quantum approaches could one day break.",
        "Provides no insight into future hardware readiness.",
    ],
    "quantum": [
        "Not deployable at this data scale or feature dimensionality.",
        "Results would not be reproducible on current noisy devices.",
        "Substantially higher cost per experiment.",
    ],
}

_NEXT_STEPS = {
    "hybrid": [
        "Train and validate the classical baseline to establish a real accuracy floor.",
        "Prototype a quantum feature-selection step on a reduced feature set.",
        "Define the fallback path so classical results are used whenever the quantum step is inconclusive.",
        "Re-run the comparison once both paths produce measured, not mocked, numbers.",
    ],
    "classical": [
        "Establish a measured baseline with cross-validated classical models.",
        "Identify the sub-problems that dominate the error budget.",
        "Re-evaluate quantum options if the feature space can be reduced sharply.",
    ],
    "quantum": [
        "Reduce the feature set until it fits a realistic qubit budget.",
        "Validate the approach on a simulator before touching hardware.",
    ],
}


def build_recommendation_block(
    comparison: dict[str, Any],
    classical: dict[str, Any],
    quantum: dict[str, Any],
    problem: dict[str, Any],
    dataset: dict[str, Any],
) -> dict[str, Any]:
    """Turn the weighted comparison into a mock recommendation card."""
    totals = comparison.get("weighted_scores", {})
    winner = comparison.get("winner", "hybrid")
    label = APPROACH_LABELS[winner]

    best = classical.get("best_model", {})
    suitability = quantum.get("suitability_score", 0)
    rows = dataset.get("rows") or 0

    reasons = [
        {
            "title": "Classical baselines are strong and cheap",
            "detail": (
                f"Standard models are expected to reach about "
                f"{best.get('accuracy', 0) * 100:.1f}% accuracy in minutes on "
                f"{rows:,} rows, with commodity CPU hardware only."
            ),
            "impact": "High",
        },
        {
            "title": "The feature space exceeds today's quantum budget",
            "detail": (
                f"With {dataset.get('column_count', '?')} columns, the dataset cannot be "
                f"encoded into a practical qubit register (suitability {suitability}/100)."
            ),
            "impact": "High",
        },
        {
            "title": "A hybrid pipeline keeps the option open",
            "detail": (
                "A quantum feature-selection or optimisation step can be evaluated "
                "now on a reduced feature set, while classical models carry production."
            ),
            "impact": "Medium",
        },
    ]

    return {
        "recommended_approach": label,
        "approach_key": winner,
        "confidence": 0.86,
        "confidence_label": "High confidence",
        "headline": f"Recommended Approach: {label}",
        "summary": (
            f"{label} is the strongest option for this problem today, driven mainly by "
            f"the maturity gap between classical and quantum approaches."
        ),
        "scores": totals,
        "reasons": reasons,
        "advantages": _BENEFITS[winner],
        "limitations": _LIMITATIONS[winner],
        "suggested_next_steps": _NEXT_STEPS[winner],
        "roadmap": [
            {"phase": "Phase 1", "title": "Establish the classical baseline", "status": "not-started"},
            {"phase": "Phase 2", "title": "Prototype the quantum sub-routine", "status": "not-started"},
            {"phase": "Phase 3", "title": "Compare measured results", "status": "blocked"},
            {"phase": "Phase 4", "title": "Production decision", "status": "blocked"},
        ],
        "decision_basis": (
            f"Derived from the weighted comparison across "
            f"{len(comparison.get('criteria', []))} criteria. "
            f"Task type: {problem.get('task_type')}."
        ),
        "confidence_in_underlying_data": "Low — all inputs are mocked.",
        "is_mock": True,
        "disclaimer": _DISCLAIMER,
    }
