"""Real local QAOA feature-relationship optimisation experiment."""

from __future__ import annotations

import csv
import io
import json
import math
import time
from pathlib import Path
from typing import Any

MAX_QUBITS = 6
MAX_PROFILED_FEATURES = 64
SAMPLE_ROWS = 250
SHOTS = 1024


class QuantumAnalysisError(RuntimeError):
    """Expected quantum-stage error that should not break the full pipeline."""


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _load_rows(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Read a small local sample; uploaded data is never sent to a cloud backend."""
    path_value = metadata.get("stored_path")
    if not path_value or not Path(path_value).is_file():
        raise QuantumAnalysisError("The uploaded dataset is unavailable for quantum analysis.")
    path = Path(path_value)
    raw = path.read_bytes()
    if not raw:
        raise QuantumAnalysisError("The uploaded dataset is empty.")
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace"))))[:SAMPLE_ROWS]
    elif path.suffix.lower() == ".json":
        parsed = json.loads(raw.decode("utf-8-sig", errors="replace"))
        rows = parsed if isinstance(parsed, list) else [parsed]
        rows = [row for row in rows[:SAMPLE_ROWS] if isinstance(row, dict)]
    else:
        raise QuantumAnalysisError("Quantum analysis currently requires a parsed CSV or JSON dataset.")
    if not rows:
        raise QuantumAnalysisError("The uploaded dataset contains no data rows.")
    return rows


def _vectors(rows: list[dict[str, Any]], names: list[str]) -> dict[str, list[float]]:
    vectors: dict[str, list[float]] = {}
    for name in names:
        raw = [row.get(name) for row in rows]
        values = [_number(value) for value in raw]
        valid = [value for value in values if value is not None]
        if len(valid) >= max(3, len(raw) // 2):
            mean = sum(valid) / len(valid)
            vectors[name] = [value if value is not None else mean for value in values]
        else:
            codes: dict[str, float] = {}
            vectors[name] = [codes.setdefault(str(value or "<missing>"), float(len(codes))) for value in raw]
    return vectors


def _variance(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _correlation(left: list[float], right: list[float]) -> float:
    lm, rm = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((a - lm) * (b - rm) for a, b in zip(left, right))
    denominator = math.sqrt(sum((a - lm) ** 2 for a in left) * sum((b - rm) ** 2 for b in right))
    return numerator / denominator if denominator else 0.0


def _graph(rows: list[dict[str, Any]], dataset: dict[str, Any]) -> tuple[list[str], list[tuple[int, int, float]]]:
    names = list(dataset.get("feature_names") or [])
    if not names:
        raise QuantumAnalysisError("No usable feature columns were found in the dataset.")
    if len(names) > MAX_PROFILED_FEATURES:
        raise QuantumAnalysisError(
            f"{len(names)} features exceed the local quantum preprocessing limit of {MAX_PROFILED_FEATURES}. "
            "Reduce features before running the simulator."
        )
    data = _vectors(rows, names)
    selected = sorted(data, key=lambda name: _variance(data[name]), reverse=True)[:MAX_QUBITS]
    if len(selected) < 2:
        raise QuantumAnalysisError("At least two variable feature columns are required for QAOA.")
    edges = []
    for left, name in enumerate(selected):
        for right in range(left + 1, len(selected)):
            # Weakly correlated features are more useful together, so their cut edge is heavier.
            edges.append((left, right, round(max(0.05, 1 - abs(_correlation(data[name], data[selected[right]]))), 4)))
    return selected, edges


def _circuit(qubits: int, edges: list[tuple[int, int, float]], gamma: float, beta: float, measure: bool):
    """Construct p=1 QAOA: H creates candidate cuts, RZZ encodes cost, RX mixes."""
    from qiskit import QuantumCircuit

    circuit = QuantumCircuit(qubits, qubits if measure else 0)
    circuit.h(range(qubits))
    for left, right, weight in edges:
        circuit.rzz(2 * gamma * weight, left, right)
    circuit.rx(2 * beta, range(qubits))
    if measure:
        circuit.measure(range(qubits), range(qubits))
    return circuit


def _cost(bits: str, edges: list[tuple[int, int, float]]) -> float:
    return sum(weight for left, right, weight in edges if bits[-1 - left] != bits[-1 - right])


def _execute(features: list[str], edges: list[tuple[int, int, float]]) -> dict[str, Any]:
    try:
        from qiskit.quantum_info import Statevector
        from qiskit_aer import AerSimulator
    except ImportError as exc:
        raise QuantumAnalysisError("Qiskit Aer is not installed. Install backend requirements to run quantum analysis.") from exc
    started = time.perf_counter()
    best: tuple[float, float, float] | None = None
    # Small deterministic grid search: 16 real circuit simulations, laptop-safe.
    for gamma in (0.2, 0.5, 0.8, 1.1):
        for beta in (0.2, 0.5, 0.8, 1.1):
            state = Statevector.from_instruction(_circuit(len(features), edges, gamma, beta, False))
            expected = sum(probability * _cost(format(index, f"0{len(features)}b"), edges) for index, probability in enumerate(state.probabilities()))
            if best is None or expected > best[0]:
                best = (expected, gamma, beta)
    assert best is not None
    expected, gamma, beta = best
    circuit = _circuit(len(features), edges, gamma, beta, True)
    counts = AerSimulator().run(circuit, shots=SHOTS, seed_simulator=7).result().get_counts()
    bitstring, count = max(counts.items(), key=lambda item: item[1])
    operations = circuit.count_ops()
    gates = sum(operations.values())
    return {"status": "completed", "algorithm": "QAOA (p=1) weighted Max-Cut feature-relationship optimisation experiment", "features": features, "qubits": len(features), "depth": circuit.depth(), "gate_count": gates, "two_qubit_gate_ratio": round(operations.get("rzz", 0) / max(gates, 1), 3), "execution_time_sec": round(time.perf_counter() - started, 4), "iterations": 16, "shots": SHOTS, "objective_value": round(sum(n / SHOTS * _cost(key, edges) for key, n in counts.items()), 5), "expected_objective_value": round(expected, 5), "best_bitstring": bitstring, "best_partition_bitstring": bitstring, "best_bitstring_count": count, "partition_interpretation": "QAOA partitions the reduced feature graph based on feature relationships. The result is an optimization signal for feature selection, not a replacement for classical predictive-model validation.", "parameters": {"gamma": gamma, "beta": beta}}


def _suitability(dataset: dict[str, Any], problem: dict[str, Any], result: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    rows, features = int(dataset.get("rows") or 0), int(dataset.get("feature_count") or 0)
    task = str(problem.get("task_type") or "Unspecified")
    factors = [
        {"factor": "Quantum formulation", "points": 30 if result else 0, "detail": "A compact QAOA Max-Cut feature-relationship formulation was executed." if result else "No executable local formulation was available."},
        {"factor": "Qubit budget", "points": 25 if result else 5, "detail": f"{result['qubits']} qubits fit the {MAX_QUBITS}-qubit simulator cap." if result else f"{features} profiled features require reduction or parsing."},
        {"factor": "Circuit complexity", "points": 20 if result and result['depth'] <= 20 else 5, "detail": f"Measured depth: {result['depth']}." if result else "No circuit depth was measured."},
        {"factor": "Dataset scale", "points": 15 if 0 < rows <= 10_000 else 5, "detail": f"{rows:,} rows are sampled classically before quantum optimisation."},
        {"factor": "Problem fit", "points": 10 if "Classification" in task or "Clustering" in task else 5, "detail": f"{task} can use feature selection as a hybrid subroutine."},
    ]
    score = sum(item["points"] for item in factors)
    level, approach = ("Potential", "Hybrid approach") if result and score >= 70 else ("Limited", "Classical computing with an optional quantum pilot") if result else ("Not currently suitable", "Classical computing")
    limits = ["This simulator result demonstrates circuit execution, not quantum advantage.", "The Max-Cut partition is an optimisation signal for feature selection, not a final selected-feature subset or a replacement for classical predictive-model validation.", "Hardware noise, queue time, and larger feature spaces can change feasibility."]
    if error:
        limits.insert(0, error)
    return {"score": score, "level": level, "recommended_approach": approach, "factors": factors, "reasons": [item["detail"] for item in factors if item["points"] >= 10], "limitations": limits}


def run(dataset: dict[str, Any], problem: dict[str, Any], analysis_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run QAOA locally, returning the existing block fields plus measured metrics."""
    del analysis_id
    result: dict[str, Any] | None = None
    error: str | None = None
    try:
        task = str(problem.get("task_type") or "")
        supported = ("Classification", "Regression", "Clustering", "Optimisation", "Optimization")
        if not any(label in task for label in supported):
            raise QuantumAnalysisError(f"Unsupported problem type for the QAOA feature-selection MVP: {task or 'unspecified'}.")
        features, edges = _graph(_load_rows(metadata or {}), dataset)
        result = _execute(features, edges)
    except (QuantumAnalysisError, OSError, json.JSONDecodeError, ValueError) as exc:
        error = str(exc)
    except Exception as exc:  # Defensive wrapper around optional simulator internals.
        error = f"Quantum execution failed: {type(exc).__name__}: {exc}"
    suitability = _suitability(dataset, problem, result, error)
    metrics = result or {"status": "not_run", "algorithm": "QAOA feature-relationship optimisation experiment (not executed)", "features": [], "qubits": 0, "depth": 0, "gate_count": 0, "two_qubit_gate_ratio": 0, "execution_time_sec": 0, "iterations": 0, "shots": 0, "objective_value": None, "expected_objective_value": None, "best_bitstring": None, "best_partition_bitstring": None, "best_bitstring_count": 0, "partition_interpretation": "No QAOA partition was produced.", "parameters": {}}
    candidate = {"name": metrics["algorithm"], "family": "Optimisation", "problem_fitting": round(suitability["score"] / 100, 2), "qubits_required": metrics["qubits"], "circuit_depth": metrics["depth"], "gate_count": metrics["gate_count"], "suitability": "high" if suitability["score"] >= 70 else "medium" if result else "exploratory", "notes": "Measured on local Qiskit Aer." if result else error}
    quantum_analysis_real = result is not None
    return {"status": metrics["status"], "error": error, "data_source": "real" if quantum_analysis_real else "unavailable", "quantum_analysis_real": quantum_analysis_real, "primary_algorithm": metrics["algorithm"], "algorithm": metrics["algorithm"], "execution": metrics, "suitability_score": suitability["score"], "suitability_label": suitability["level"], "suitability": suitability, "recommended_approach": suitability["recommended_approach"], "qubits_required": metrics["qubits"], "qubits_estimate_range": f"0-{MAX_QUBITS}", "circuit_complexity": {"depth": metrics["depth"], "gate_count": metrics["gate_count"], "two_qubit_gate_ratio": metrics["two_qubit_gate_ratio"], "summary": "Measured from the executed p=1 QAOA circuit." if result else "No circuit was executed."}, "estimated_resources": {"provider": "Qiskit Aer local simulator", "required_qubits": metrics["qubits"], "expected_queue_time": "None (local)", "shots": metrics["shots"], "cost_per_shot": "No cloud cost", "notes": "The simulator uses the local Python process."}, "feasibility": "Executed locally" if result else "Not executable with current input", "confidence": 1.0 if result else 0.0, "candidate_algorithms": [candidate], "potential_advantages": ["Tests a real quantum optimisation circuit on a compact, data-derived graph.", "Keeps raw data and predictive modelling in the classical pipeline."], "limitations": suitability["limitations"], "encoding_strategies": ["Computational-basis bitstrings for feature partitions"], "is_mock": False, "note": "Circuit metrics and objective values are measured locally with Qiskit Aer; suitability uses the explicit factor table."}
