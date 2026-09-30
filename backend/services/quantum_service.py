"""Stage 4 — quantum suitability analysis (scoring only, no fabricated results).

    ############################################################
    #  THIS STAGE NEVER CLAIMS A QUANTUM ADVANTAGE.           #
    #  It scores how *worth investigating* a problem is with    #
    #  quantum methods. It does not predict performance, and   #
    #  it does not run a circuit against hardware.             #
    ############################################################

The score
---------
``suitability_score`` is a weighted sum of six normalised factors, each in
``[0, 1]``, each a documented function of a *measurable* property of the data::

    raw   = sum(weight_i * factor_i)          for i in 1..6,  sum(weight_i) = 1.0
    score = 100 * min(raw, 1.0), then hard caps are applied

    +-------------------------+-------+---------------------------------+
    | factor                  | wt    | normalised from                 |
    +=========================+=======+=================================+
    | optimization_suitability| 0.20  | problem framing (measured: task|
    |                         |       | type + keyword evidence)        |
    | search_space_complexity | 0.20  | log2(2^d) = d, over 64 features |
    | feature_dimensionality  | 0.12  | peak for d <= 8, zero at d = 64 |
    | dataset_size_compat     | 0.18  | rows, over a log scale 500..10k |
    | encoding_feasibility    | 0.15  | cardinality blow-up, missing %, |
    |                         |       | id-like columns                 |
    | hardware_feasibility    | 0.15  | qubits needed / reference budget|
    +-------------------------+-------+---------------------------------+

Two **hard caps** then apply, because a weighted average is too forgiving of a
single disqualifying fact:

* more qubits than the reference device budget  -> capped at 25
* a wide, purely predictive problem with no optimisation structure -> capped at 35

The full factor table is returned in ``quantum_analysis.scoring.factors`` so the
number is auditable, and ``score_interpretation`` states in the payload what the
score does and does not mean.
"""

from __future__ import annotations

import importlib.util
from typing import Any

from config import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)

#: Factor weights. Must sum to 1.0 (asserted at import).
FACTOR_WEIGHTS: dict[str, float] = {
    "optimization_suitability": 0.20,
    "search_space_complexity": 0.20,
    "feature_dimensionality": 0.12,
    "dataset_size_compatibility": 0.18,
    "encoding_feasibility": 0.15,
    "hardware_feasibility": 0.15,
}

#: Feature count at which the 2^d selection space is treated as "as large as we score".
SEARCH_SPACE_REFERENCE_FEATURES = 64
#: Feature count at which angle encoding stops being credible.
ENCODING_FEATURE_CEILING = 64
#: Row counts bracketing the shot-cost penalty.
SAMPLE_COMFORTABLE = 500
SAMPLE_CEILING = 10_000

SCORE_INTERPRETATION = (
    "This score answers: 'how suitable is this problem for investigating quantum "
    "methods?' It does NOT answer: 'quantum will outperform classical AI here.' "
    "No quantum circuit was executed and no quantum performance figure is claimed."
)

assert abs(sum(FACTOR_WEIGHTS.values()) - 1.0) < 1e-9, "Factor weights must sum to 1.0"


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _ramp(value: float, best: float, worst: float) -> float:
    """Linear ramp: 1.0 at ``best``, 0.0 at ``worst`` (either order allowed)."""
    if best == worst:
        return 1.0
    return _clamp((value - worst) / (best - worst))


def available_framework() -> str | None:
    """Return an installed quantum framework name, or ``None``.

    Detection only - importing is cheap and guarded, and the absence of a
    framework never degrades the analysis, because the analysis is theoretical.
    """
    for name in ("qiskit", "pennylane"):
        try:
            if importlib.util.find_spec(name) is not None:
                return name
        except (ImportError, ValueError):  # pragma: no cover - defensive
            continue
    return None


# --------------------------------------------------------------------------
# Factors
# --------------------------------------------------------------------------


def _optimization_suitability(problem: dict[str, Any]) -> tuple[float, str]:
    """How much genuine optimisation / combinatorial-search structure is present."""
    problem_type = problem.get("problem_type", "unknown")
    scores = (problem.get("detection") or {}).get("keyword_scores") or {}
    keyword_hits = int(scores.get("optimization", 0))

    if problem_type == "optimization":
        value = 1.0
        reason = "The problem is explicitly framed as an optimisation/search task."
    elif keyword_hits >= 1:
        value = 0.8
        reason = (
            f"The problem statement carries {keyword_hits} optimisation cue(s), which "
            "suggests a search sub-problem even though the task type is not optimisation."
        )
    elif problem_type in ("classification", "regression"):
        # A predictive task still contains a feature-selection sub-problem, but
        # it is a weak, already well-solved-by-classicals argument.
        value = 0.45
        reason = (
            "Predictive task: a feature-selection sub-problem exists, but the end-to-end "
            "problem is not a search problem."
        )
    elif problem_type == "clustering":
        value = 0.35
        reason = "Clustering has a mild combinatorial assignment structure."
    else:
        value = 0.15
        reason = "No optimisation structure was identified in the data or the statement."
    return value, reason


def _search_space_complexity(d: int) -> tuple[float, str]:
    """The feature-selection search space has 2**d members; normalise over 64 features."""
    value = _clamp(d / SEARCH_SPACE_REFERENCE_FEATURES)
    log2 = float(d)
    reason = (
        f"Selecting a subset of {d} features means searching {log2:.0f} bits of "
        f"solution space (2^{int(d)} candidate subsets)."
    )
    return value, reason


def _feature_dimensionality(d: int) -> tuple[float, str]:
    """Quantum encodings need few features; score peaks at d <= 8 and dies by 64."""
    if d <= 8:
        value = 1.0
    else:
        value = _clamp(1.0 - (d - 8) / (ENCODING_FEATURE_CEILING - 8))
    reason = (
        f"{d} features. Angle encoding needs one qubit per feature, so the sweet spot "
        "is 8 or fewer; beyond 64 features a qubit register cannot hold the data."
    )
    return value, reason


def _dataset_size_compatibility(rows: int) -> tuple[float, str]:
    """Shot-based training cost grows with n (and quadratically for kernels)."""
    if rows <= SAMPLE_COMFORTABLE:
        value = 1.0
    elif rows >= SAMPLE_CEILING:
        value = 0.0
    else:
        # Log scale between the two anchors.
        import math

        low = math.log10(SAMPLE_COMFORTABLE)
        high = math.log10(SAMPLE_CEILING)
        value = _clamp(1.0 - (math.log10(rows) - low) / (high - low))
    reason = (
        f"{rows:,} rows. Variational training is shot-based, so cost scales with the "
        "number of samples; quantum kernels additionally need an n x n similarity matrix."
    )
    return value, reason


def _encoding_feasibility(dataset: dict[str, Any], d: int) -> tuple[float, str]:
    """How cleanly the data can be mapped onto a qubit register.

    Only *categorical* columns are penalised for cardinality. A continuous
    column has a distinct value per row by nature, and angle encoding handles
    that perfectly well - counting it as an encoding problem would penalise
    healthy numeric data.
    """
    categorical, _, id_like, high_card = _feature_columns(dataset)
    cardinality = dataset.get("feature_cardinality") or {}
    categorical_set = set(categorical)
    score = 1.0
    penalties: list[str] = []

    # One-hot blow-up: a categorical column with k levels costs k qubits.
    one_hot_qubits = sum(min(int(cardinality.get(c, 2)), 64) for c in categorical)
    if one_hot_qubits > max(2 * d, 16):
        excess = one_hot_qubits - max(2 * d, 16)
        score -= min(0.35, 0.02 * excess)
        penalties.append(
            f"One-hot encoding of the categorical features needs about "
            f"{one_hot_qubits} qubits."
        )

    # Identifier-like / free-text categoricals have no bounded encoding.
    bad_cardinality = [c for c in high_card + id_like if c in categorical_set]
    if bad_cardinality:
        score -= min(0.3, 0.06 * len(bad_cardinality))
        penalties.append(
            f"{len(bad_cardinality)} categorical column(s) are identifier-like or "
            "free-text and would dominate the register; they must be dropped, "
            "hashed or binned first."
        )

    # Missing values have no native representation on a qubit.
    missing_pct = dataset.get("missing_percent") or 0.0
    if missing_pct > 5:
        score -= min(0.3, missing_pct / 100.0)
        penalties.append(
            f"{missing_pct}% of cells are missing and need imputation before encoding."
        )

    reason = (
        "Data maps onto a qubit register without significant preprocessing."
        if not penalties
        else "Encoding needs preprocessing: " + " ".join(penalties)
    )
    return _clamp(score), reason


def _hardware_feasibility(qubits: int) -> tuple[float, str]:
    """Required qubits against the reference device budget."""
    budget = max(1, settings.quantum_reference_qubits)
    value = _clamp(1.0 - (qubits / budget))
    reason = (
        f"{qubits} qubit(s) required against a reference budget of {budget} publicly "
        "available qubits. This is a published capability reference, not a measurement "
        "of any particular device."
    )
    return value, reason


# --------------------------------------------------------------------------
# Encoding / qubit estimation
# --------------------------------------------------------------------------


def _feature_columns(dataset: dict[str, Any]) -> tuple[list[str], list[str], list[str], list[str]]:
    """Columns usable as model *input*.

    The target column is excluded everywhere: it is never encoded into the
    register as an input feature, and counting it (for example one-hot encoding
    a 2-level label) would understate the qubit cost of the real feature set.
    """
    target = dataset.get("target_column")

    def drop_target(names: Any) -> list[str]:
        return [c for c in (names or []) if c != target]

    return (
        drop_target(dataset.get("categorical_columns")),
        drop_target(dataset.get("numerical_columns")),
        drop_target(dataset.get("id_like_features")),
        drop_target(dataset.get("high_cardinality_features")),
    )


#: Above this many features, amplitude encoding is never recommended even
#: though it uses few qubits, because state preparation dominates the circuit.
AMPLITUDE_ENCODING_FEATURE_LIMIT = 8


def estimate_qubits(dataset: dict[str, Any], d: int) -> dict[str, Any]:
    """Qubit cost of each standard data-encoding strategy.

    All three are reported rather than only the flattering one, because the
    choice of encoding is the single largest driver of feasibility:

    * **angle** - 1 qubit per feature. Linear, and no state preparation.
    * **one-hot** - 1 qubit per level of every categorical *input* feature.
    * **amplitude** - ceil(log2 d) qubits, which *looks* tiny but needs a state
      preparation costing ~max(0, 2**n - d) swap gates (Nielsen & Chuang), so it
      is only credible for a handful of features.

    The recommended strategy is the cheapest *credible* one, not simply the
    smallest number: amplitude encoding is only recommended for d <= 8.
    """
    import math

    categorical, _, _, _ = _feature_columns(dataset)
    cardinality = dataset.get("feature_cardinality") or {}
    one_hot = sum(min(int(cardinality.get(c, 2)), 64) for c in categorical) or d

    amplitude_qubits = max(1, math.ceil(math.log2(max(2, d))))
    amplitude_swaps = max(0, 2**amplitude_qubits - d)

    angle = ("Angle encoding", d, "1 qubit per feature; no state preparation.")
    one_hot_entry = ("One-hot (dense) encoding", min(one_hot, 4096), "1 qubit per category level.")
    amplitude = (
        "Amplitude encoding",
        amplitude_qubits,
        f"ceil(log2 {d}) qubits, but ~{amplitude_swaps:,} swap gates of state preparation.",
    )

    if d <= AMPLITUDE_ENCODING_FEATURE_LIMIT and amplitude_swaps <= 16:
        recommended = amplitude
    else:
        recommended = min((angle, one_hot_entry), key=lambda entry: entry[1])

    return {
        "strategies": [angle[0], one_hot_entry[0], amplitude[0]],
        "qubits": {
            angle[0]: angle[1],
            one_hot_entry[0]: one_hot_entry[1],
            amplitude[0]: amplitude[1],
        },
        "details": {angle[0]: angle[2], one_hot_entry[0]: one_hot_entry[2], amplitude[0]: amplitude[2]},
        "recommended": recommended[0],
        "recommended_qubits": recommended[1],
        "angle_encoding_qubits": d,
        "one_hot_qubits": min(one_hot, 4096),
        "amplitude_encoding_qubits": amplitude_qubits,
        "amplitude_state_preparation_swaps": amplitude_swaps,
        "categorical_input_columns": categorical,
        "difficulty": (
            "Low" if recommended[1] <= 16
            else "Moderate" if recommended[1] <= ENCODING_FEATURE_CEILING
            else "High"
        ),
        "explanation": (
            f"{d} features, {len(categorical)} categorical input column(s). "
            f"{recommended[0]} is the cheapest credible encoding at "
            f"{recommended[1]} qubit(s). "
            + (
                "That fits the reference qubit budget."
                if recommended[1] <= settings.quantum_reference_qubits
                else "That exceeds the reference qubit budget, so feature reduction "
                "would be required before any quantum step."
            )
        ),
    }


# --------------------------------------------------------------------------
# Candidate methods
# --------------------------------------------------------------------------


def _candidate_methods(
    problem_type: str, d: int, rows: int, qubits: int, optimization_hits: int
) -> list[dict[str, Any]]:
    """Rank candidate quantum methods for this problem.

    ``problem_fitting`` is a transparent 0-1 relevance score built from the same
    measurements as the factors - it is *not* a predicted accuracy.
    """
    # 1. Quantum feature selection: the strongest generic candidate, because
    #    2**d really is a combinatorial search even when the task is predictive.
    fs_fit = 0.85
    if d > 64:
        fs_fit = 0.6
    elif d < 12:
        fs_fit = 0.6
    methods = [
        {
            "name": "Quantum Feature Selection",
            "family": "Optimisation",
            "qubits_required": min(qubits, 64),
            "circuit_depth": 4,
            "gate_count": 8 * max(1, min(qubits, 64)),
            "two_qubit_gate_ratio": 0.5,
            "problem_fitting": fs_fit,
            "notes": (
                "QAOA-based subset search over the 2^d feature space. The most "
                "defensible candidate here, because the search space is genuinely "
                "combinatorial and a classical backbone can evaluate any answer."
            ),
            "rationale": f"Feature-selection search space is 2^{d} subsets.",
            "blocking_issues": (
                ["Requires a qubit per candidate feature - a reduction step is needed first."]
                if qubits > 64
                else []
            ),
        }
    ]

    # 2. QAOA proper: only relevant when the problem really is an optimisation.
    if problem_type == "optimization" or optimization_hits >= 2:
        methods.append(
            {
                "name": "QAOA",
                "family": "Optimisation",
                "qubits_required": min(max(qubits, 2), 64),
                "circuit_depth": 8,
                "gate_count": 12 * min(max(qubits, 2), 64),
                "two_qubit_gate_ratio": 0.55,
                "problem_fitting": 0.9 if problem_type == "optimization" else 0.7,
                "notes": (
                    "Quantum Approximate Optimisation Algorithm for a constrained "
                    "combinatorial objective (scheduling, routing, subset choice)."
                ),
                "rationale": "The problem is framed as an optimisation/search task.",
                "blocking_issues": (
                    []
                    if qubits <= 64
                    else ["The decision vector exceeds a practical qubit register."]
                ),
            }
        )

    # 3. Variational classifier: credible only for small, low-dimensional data.
    if problem_type == "classification":
        small = d <= 24 and rows <= 2000
        methods.append(
            {
                "name": "VQC (Variational Quantum Classifier)",
                "family": "Kernel / Variational",
                "qubits_required": min(qubits, 64),
                "circuit_depth": 6,
                "gate_count": 18 * min(qubits, 64),
                "two_qubit_gate_ratio": 0.35,
                "problem_fitting": 0.75 if small else 0.35,
                "notes": (
                    "Trainable circuit + measurement, small parameter count. "
                    + (
                        "Feature and sample counts are in the range where a simulator "
                        "experiment is at least tractable."
                        if small
                        else "Feature/sample counts are well beyond what variational "
                        "training can handle today."
                    )
                ),
                "rationale": "Supervised classification can be expressed as a variational circuit.",
                "blocking_issues": (
                    []
                    if small
                    else [
                        "Too many features for angle encoding at this scale."
                        if d > 24
                        else "Too many samples for shot-based variational training."
                    ]
                ),
            }
        )

    # 4. Quantum kernel: the kernel matrix is the bottleneck, not the qubits.
    if problem_type in ("classification", "regression"):
        small_n = rows <= 1000
        methods.append(
            {
                "name": "Quantum Kernel (QSVM)",
                "family": "Kernel",
                "qubits_required": min(qubits, 64),
                "circuit_depth": 4,
                "gate_count": 10 * min(qubits, 64),
                "two_qubit_gate_ratio": 0.3,
                "problem_fitting": 0.6 if small_n and d <= 24 else 0.3,
                "notes": (
                    "Kernel methods map data into a quantum feature space. Requires an "
                    f"n x n similarity matrix, so cost grows quadratically in "
                    f"{rows:,} samples."
                ),
                "rationale": "A supervised task can use a quantum kernel in place of an RBF kernel.",
                "blocking_issues": (
                    []
                    if small_n
                    else [
                        f"An n x n kernel matrix over {rows:,} samples is not practical."
                    ]
                ),
            }
        )

    for method in methods:
        fit = method["problem_fitting"]
        method["suitability"] = "high" if fit >= 0.75 else "medium" if fit >= 0.5 else "exploratory"
    methods.sort(key=lambda m: m["problem_fitting"], reverse=True)
    return methods[: settings.quantum_max_methods]


def score_suitability(dataset: dict[str, Any], problem: dict[str, Any]) -> dict[str, Any]:
    """Compute the transparent quantum suitability score and its audit trail."""
    d = int((problem.get("characteristics") or {}).get("features") or dataset.get("feature_count") or 0)
    rows = int((problem.get("characteristics") or {}).get("rows") or dataset.get("rows") or 0)
    problem_type = problem.get("problem_type", "unknown")
    optimization_hits = int(
        ((problem.get("detection") or {}).get("keyword_scores") or {}).get("optimization", 0)
    )

    encoding = estimate_qubits(dataset, d)
    qubits = int(encoding["recommended_qubits"])

    factors: list[dict[str, Any]] = []

    def add(key: str, label: str, pair: tuple[float, str], unit: str) -> float:
        value, reason = pair
        weight = FACTOR_WEIGHTS[key]
        factors.append(
            {
                "key": key,
                "label": label,
                "raw_value": unit,
                "normalised": round(value, 4),
                "weight": weight,
                "contribution": round(value * weight, 4),
                "explanation": reason,
            }
        )
        return value * weight

    total = 0.0
    total += add("optimization_suitability", "Optimization suitability",
                 _optimization_suitability(problem), "categorical")
    total += add("search_space_complexity", "Search-space complexity",
                 _search_space_complexity(d), f"d = {d}")
    total += add("feature_dimensionality", "Feature dimensionality",
                 _feature_dimensionality(d), f"d = {d}")
    total += add("dataset_size_compatibility", "Dataset size compatibility",
                 _dataset_size_compatibility(rows), f"n = {rows}")
    total += add("encoding_feasibility", "Encoding feasibility",
                 _encoding_feasibility(dataset, d), "categorical")
    total += add("hardware_feasibility", "Hardware feasibility",
                 _hardware_feasibility(qubits), f"qubits = {qubits}")

    raw_score = _clamp(total)
    caps: list[dict[str, Any]] = []
    capped = raw_score
    if qubits > settings.quantum_reference_qubits:
        capped = min(capped, 0.25)
        caps.append({
            "cap": 25,
            "why": (
                f"{qubits} qubits required exceeds the reference budget of "
                f"{settings.quantum_reference_qubits}."
            ),
        })
    if problem_type in ("classification", "regression") and d > ENCODING_FEATURE_CEILING:
        capped = min(capped, 0.35)
        caps.append({
            "cap": 35,
            "why": (
                f"{d} features with no optimisation framing: too wide to encode and no "
                "combinatorial structure to exploit."
            ),
        })

    return {
        "raw_score": round(raw_score * 100, 1),
        "suitability_score": int(round(capped * 100)),
        "caps_applied": caps,
        "factors": factors,
        "encoding": encoding,
        "qubits": qubits,
        "features": d,
        "rows": rows,
        "problem_type": problem_type,
        "optimization_hits": optimization_hits,
    }


def run(
    dataset: dict[str, Any],
    problem: dict[str, Any],
    analysis_id: str = "",
    frame: Any | None = None,
) -> dict[str, Any]:
    """Produce the ``quantum_analysis`` block for an analysis run.

    No circuit is built and no hardware is contacted. The block reports how
    suitable the problem is for *investigating* quantum methods, together with
    the full factor breakdown behind that number.
    """
    scored = score_suitability(dataset, problem)
    score = scored["suitability_score"]
    encoding = scored["encoding"]
    qubits = scored["qubits"]
    d = scored["features"]
    rows = scored["rows"]
    methods = _candidate_methods(
        scored["problem_type"], d, rows, qubits, scored["optimization_hits"]
    )
    primary = methods[0] if methods else None

    if score >= 70:
        label, feasibility = "High", "Feasible on current simulators"
    elif score >= 45:
        label, feasibility = "Moderate", "Simulator-only; hardware constrained"
    else:
        label, feasibility = "Low", "Not viable on current hardware"

    framework = available_framework()
    reasoning = [f["explanation"] for f in scored["factors"]]
    if scored["caps_applied"]:
        reasoning += ["Score capped: " + c["why"] for c in scored["caps_applied"]]

    limitations = [
        "No quantum circuit was built, executed or benchmarked for this analysis.",
        "Current devices are too noisy for reliable end-to-end tabular models; "
        "results from them would not be reproducible.",
        "Variational training suffers from barren plateaus, so a small pilot can "
        "easily fail to converge for reasons unrelated to the problem.",
        "No demonstrated quantum advantage exists for this problem class today.",
    ]
    if qubits > settings.quantum_reference_qubits:
        limitations.insert(
            0,
            f"The problem needs about {qubits} qubits, above the "
            f"{settings.quantum_reference_qubits}-qubit reference budget, so feature "
            "reduction would be mandatory first.",
        )
    if d > 16:
        limitations.append(
            f"At {d} features, data-loading circuits grow linearly and the encoding "
            "overhead can outweigh any benefit of the quantum step."
        )

    advantages: list[str] = []
    if scored["problem_type"] == "optimization":
        advantages.append(
            "The problem is a combinatorial search, which is the one setting where "
            "quantum optimisation algorithms are structurally aimed."
        )
    if d >= 20:
        advantages.append(
            f"The 2^{d} feature-selection space is large enough that a quantum "
            "annealer or QAOA formulation is worth prototyping as a research question."
        )
    if rows <= 500 and d <= 12:
        advantages.append(
            "The dataset is small enough that a simulator experiment would finish in "
            "minutes, so a pilot is cheap to run."
        )
    if not advantages:
        advantages.append(
            "A pilot on a simulator would be cheap and would give a concrete, "
            "measurable answer about whether to keep investing in this direction."
        )

    circuit = primary or {"circuit_depth": 0, "gate_count": 0, "two_qubit_gate_ratio": 0.0}
    return {
        # --- existing frontend contract (names unchanged) ---
        "suitability_score": score,
        "suitability_label": label,
        "confidence": round(_clamp(0.45 + 0.4 * scored["raw_score"], 0.2, 0.9), 2),
        "candidate_algorithms": methods,
        "primary_algorithm": primary["name"] if primary else "None identified",
        "qubits_required": qubits,
        "qubits_estimate_range": f"{max(1, qubits - 6)}-{qubits + 8}",
        "circuit_complexity": {
            "depth": circuit["circuit_depth"],
            "gate_count": circuit["gate_count"],
            "two_qubit_gate_ratio": circuit["two_qubit_gate_ratio"],
            "summary": (
                f"Estimate for {primary['name']} if it were implemented. No such "
                "circuit was built."
                if primary
                else "No candidate circuit applies to this problem."
            ),
        },
        "estimated_resources": {
            "provider": (
                f"{framework} (local simulation only)" if framework
                else "No quantum framework installed; analysis is theoretical"
            ),
            "required_qubits": qubits,
            "expected_queue_time": "n/a - no hardware was contacted",
            "shots": 4096,
            "cost_per_shot": "n/a - nothing was run",
            "notes": (
                "These are planning figures for a hypothetical pilot, not a "
                "measurement and not a hardware allocation."
            ),
        },
        "feasibility": feasibility,
        "potential_advantages": advantages,
        "limitations": limitations,
        "encoding_strategies": encoding["strategies"],
        "is_mock": False,
        "note": (
            "Scored from measured dataset and problem properties. This is a "
            "theoretical suitability analysis, not an executed quantum experiment."
        ),
        # --- transparency / honesty surface ---
        "score_interpretation": SCORE_INTERPRETATION,
        "scoring": {
            "formula": (
                "score = 100 * min(1, sum(weight_i * factor_i)), then hard caps"
            ),
            "weights": FACTOR_WEIGHTS,
            "factors": scored["factors"],
            "raw_score": scored["raw_score"],
            "caps_applied": scored["caps_applied"],
        },
        "potential_methods": [m["name"] for m in methods],
        "reasoning": reasoning,
        "encoding": encoding,
        "search_space": {
            "feature_subsets_log2": float(d),
            "feature_subsets": 2**d if d <= 512 else None,
            "note": "2^d is the number of candidate feature subsets to search over.",
        },
        "execution": {
            "mode": "theoretical-suitability-analysis",
            "framework": framework,
            "framework_available": framework is not None,
            "hardware_executed": False,
            "statement": (
                "No quantum circuit was executed. This is an analysis of whether "
                "quantum methods are worth investigating for this problem, not a "
                "measurement of quantum performance."
            ),
        },
    }
