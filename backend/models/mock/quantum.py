"""Mock quantum-suitability block. No circuit is built or executed."""

from __future__ import annotations

from typing import Any

from .common import MOCK_NOTE, rnd, rng_for

QUANTUM_CATALOGUE = [
    ("VQC (Variational Quantum Classifier)", "Kernel / Variational", 18, 34, 268, 0.82,
     "Strong fit for small, low-dimensional tabular classification."),
    ("QSVM (Quantum Kernel SVM)", "Kernel", 24, 52, 612, 0.71,
     "Expressive kernels, but the feature map scales quadratically with feature count."),
    ("QAOA (Quantum Approximate Optimisation)", "Optimisation", 14, 28, 196, 0.55,
     "Applies to the feature-selection sub-problem rather than end-to-end prediction."),
    ("Quantum Neural Network (QNN)", "Variational", 20, 44, 388, 0.63,
     "Possible for compact embeddings; training noise remains a blocker."),
]


def build_quantum_block(
    dataset: dict[str, Any], problem: dict[str, Any], seed: str
) -> dict[str, Any]:
    """Score quantum suitability from the dataset shape and list candidate algorithms."""
    rng = rng_for(f"quantum::{seed}")
    columns = dataset.get("column_count") or 20
    rows = dataset.get("rows") or 5000

    # Suitability falls off as the feature space grows past what today's
    # hardware can encode — this mirrors the real scaling limit.
    raw = 96 - (columns * 1.9) - (0.9 if rows > 100000 else 0)
    suitability = int(max(18, min(94, raw + rng.uniform(-6, 6))))

    if suitability >= 70:
        label, feasibility = "High", "Feasible on current simulators"
    elif suitability >= 45:
        label, feasibility = "Moderate", "Simulator-only; hardware constrained"
    else:
        label, feasibility = "Low", "Not viable on current hardware"

    algorithms = [
        {
            "name": name,
            "family": family,
            "problem_fitting": fit,
            "qubits_required": qubits + rng.randint(-2, 4),
            "circuit_depth": depth,
            "gate_count": gates,
            "two_qubit_gate_ratio": rnd(rng.uniform(0.18, 0.46)),
            "suitability": "high" if fit >= 0.8 else "medium" if fit >= 0.6 else "exploratory",
            "notes": note,
        }
        for name, family, qubits, depth, gates, fit, note in QUANTUM_CATALOGUE
    ]
    primary = algorithms[0]

    return {
        "suitability_score": suitability,
        "suitability_label": label,
        "confidence": rnd(0.55 + suitability / 300),
        "candidate_algorithms": algorithms,
        "primary_algorithm": primary["name"],
        "qubits_required": primary["qubits_required"],
        "qubits_estimate_range": f"{primary['qubits_required'] - 6}–{primary['qubits_required'] + 8}",
        "circuit_complexity": {
            "depth": primary["circuit_depth"],
            "gate_count": primary["gate_count"],
            "two_qubit_gate_ratio": primary["two_qubit_gate_ratio"],
            "summary": "Shallow enough to simulate, deep enough to be noise-sensitive.",
        },
        "estimated_resources": {
            "provider": "IBM Quantum (simulated)",
            "required_qubits": primary["qubits_required"],
            "expected_queue_time": "Minutes (simulator)",
            "shots": 4096,
            "cost_per_shot": "Free tier",
            "notes": "No real hardware allocation is requested by the prototype.",
        },
        "feasibility": feasibility,
        "potential_advantages": [
            "Compact kernel may capture non-linear structure with few parameters.",
            "Possible speed-up on specific sampling / optimisation sub-routines.",
            "Reduced parameter count suits small, low-dimensional feature spaces.",
        ],
        "limitations": [
            "Feature count must be compressed to fit a small qubit register.",
            "Barren plateaus make variational training unstable without careful design.",
            "Current devices are too noisy for reliable end-to-end tabular models.",
            "No demonstrated quantum advantage for this problem class today.",
        ],
        "encoding_strategies": ["Angle encoding", "Amplitude encoding", "One-hot (dense) encoding"],
        "is_mock": True,
        "note": MOCK_NOTE,
    }
