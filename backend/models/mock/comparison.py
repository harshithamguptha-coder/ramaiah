"""Mock three-way comparison matrix: Classical AI vs Quantum AI vs Hybrid AI."""

from __future__ import annotations

from typing import Any

from .common import APPROACH_LABELS, MOCK_NOTE

APPROACH_KEYS = ("classical", "quantum", "hybrid")


def _cell(score: int, value: str, note: str) -> dict[str, Any]:
    return {"score": int(score), "value": value, "note": note}


def _row(criterion: str, weight: float, scores: dict[str, int]) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "weight": weight,
        **{key: {"score": int(score)} for key, score in scores.items()},
    }


def build_comparison_block(
    classical: dict[str, Any], quantum: dict[str, Any], dataset: dict[str, Any]
) -> dict[str, Any]:
    """Build the weighted comparison matrix and the radar-chart series."""
    best_accuracy = classical.get("best_model", {}).get("accuracy", 0.9) * 100
    suitability = quantum.get("suitability_score", 50)
    rows = dataset.get("rows") or 5000

    criteria = [
        {
            "criterion": "Accuracy / Precision", "weight": 0.30,
            "classical": _cell(best_accuracy, f"{best_accuracy:.1f}% (expected)",
                               "Well-established and measurable today."),
            "quantum": _cell(max(5, int(suitability * 0.6)), "Unproven",
                             "No reproducible end-to-end result at this scale."),
            "hybrid": _cell(best_accuracy - 1, f"~{best_accuracy - 1:.1f}% (expected)",
                            "Classical backbone with quantum feature selection."),
        },
        {
            "criterion": "Computational Complexity", "weight": 0.15,
            "classical": _cell(92, "Polynomial", "Predictable scaling on CPU."),
            "quantum": _cell(35, "Exponential (state space)", "2ⁿ states dominate cost."),
            "hybrid": _cell(78, "Polynomial + isolated quantum step", "Only one sub-routine is quantum."),
        },
        {
            "criterion": "Training Time", "weight": 0.15,
            "classical": _cell(95, "Seconds to minutes", "Negligible at this data scale."),
            "quantum": _cell(25, "Hours (simulated)", "Shot-based sampling is slow."),
            "hybrid": _cell(70, "Minutes", "Only the selected sub-routine pays the cost."),
        },
        {
            "criterion": "Scalability", "weight": 0.10,
            "classical": _cell(88, "Millions of rows", "Bounded by memory and cost."),
            "quantum": _cell(30, "≤ 10² rows", "Qubit budgets cannot absorb real datasets."),
            "hybrid": _cell(76, "Sample-level quantum use", "Quantum step sees a reduced set."),
        },
        {
            "criterion": "Hardware Requirements", "weight": 0.10,
            "classical": _cell(96, "CPU / commodity GPU", "Widely available."),
            "quantum": _cell(15, "QPU access required", "Limited, noisy, expensive."),
            "hybrid": _cell(72, "CPU + simulator", "A simulator is enough for a pilot."),
        },
        {
            "criterion": "Data Size Suitability", "weight": 0.10,
            "classical": _cell(94 if rows < 100000 else 78, f"{rows:,} rows",
                               "Fits comfortably in memory."),
            "quantum": _cell(22, "≤ 10² rows", "Beyond current qubit budgets."),
            "hybrid": _cell(80, "Sample-level quantum use", "Hybrid keeps the data path classical."),
        },
        {
            "criterion": "Optimisation Potential", "weight": 0.05,
            "classical": _cell(70, "Convex / gradient methods", "Well-understood optimisers."),
            "quantum": _cell(80, "Native combinatorial search", "Promising but immature."),
            "hybrid": _cell(84, "Best of both", "Quantum optimiser inside a classical loop."),
        },
        {
            "criterion": "Quantum Feasibility (today)", "weight": 0.05,
            "classical": _cell(100, "N/A — fully deployable", "Production-ready."),
            "quantum": _cell(suitability, f"{suitability}/100", "Simulator-only for now."),
            "hybrid": _cell(max(40, int(suitability * 0.8)), "Pilot-ready",
                            "Classical fallback keeps it safe."),
        },
    ]

    totals = {
        key: round(sum(c[key]["score"] * c["weight"] for c in criteria), 1)
        for key in APPROACH_KEYS
    }
    winner = max(totals, key=lambda k: totals[k])
    axes = [c["criterion"] for c in criteria]

    return {
        "criteria": criteria,
        "weights": {c["criterion"]: c["weight"] for c in criteria},
        "weighted_scores": totals,
        "winner": winner,
        "winner_label": APPROACH_LABELS[winner],
        "radar_axes": axes,
        "radar_series": [
            {
                "key": key,
                "label": APPROACH_LABELS[key],
                "values": [c[key]["score"] for c in criteria],
            }
            for key in APPROACH_KEYS
        ],
        "summary": (
            f"{APPROACH_LABELS[winner]} leads the weighted comparison at "
            f"{totals[winner]}/100, with classical AI holding a clear advantage on "
            "everything that is executable with today's technology."
        ),
        "is_mock": True,
        "note": MOCK_NOTE,
    }
