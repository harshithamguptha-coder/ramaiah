"""Stage 6 — the recommendation engine (explicit decision rules, not a vote).

    ############################################################
    #  The default answer is Classical AI.                     #
    #  Quantum AI must be *earned* by clearing every gate.     #
    ############################################################

Unlike the previous placeholder, this stage does not simply pick the winner of
the weighted comparison. It applies an ordered set of gates, and returns the
first one that matches, together with the evidence that matched it.

Gates (evaluated in order)
-------------------------
G1  No classical baseline was measured and no quantum candidate is feasible
    -> **Classical**, flagged as a data problem rather than a technology verdict.
G2  A classical model was measured and quantum suitability is below
    ``LOW_SUITABILITY`` (30) -> **Classical**: quantum is not worth the spend.
G3  Quantum suitability is at or above ``HIGH_SUITABILITY`` (70) **and** the
    register fits in ``QUANTUM_QUBIT_BUDGET`` (32) qubits **and** (the problem
    is an optimisation task **or** the classical result is weak/missing) **and**
    at least one candidate method has no blocking issue -> **Quantum**.
G4  A classical backbone exists and suitability sits in the *investigable* band
    (30-85) with a concrete quantum sub-step -> **Hybrid**.
G5  Otherwise -> **Classical**.

G3 is deliberately hard to pass. In the current hardware landscape it is
expected to fail, and that is the correct outcome: the rules are written to
change as evidence accumulates, not to reach a predetermined answer.
"""

from __future__ import annotations

from typing import Any

from config import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)

APPROACH_LABELS = {
    "classical": "Classical AI",
    "quantum": "Quantum AI",
    "hybrid": "Hybrid AI",
}

#: Below this suitability, quantum methods are not worth investigating at all.
LOW_SUITABILITY = 30
#: Quantum AI is only ever considered at or above this suitability.
HIGH_SUITABILITY = 70
#: A register this small is the only one that is plausibly runnable today.
QUANTUM_QUBIT_BUDGET = 32
#: Classical quality below this counts as "weak" for gate G3.
WEAK_CLASSICAL_QUALITY = 0.60
#: A quantum experiment needs at least this many rows to be worth running at all.
MIN_EXPERIMENT_ROWS = 30

BENEFITS = {
    "classical": [
        "Fastest path to production; no new infrastructure is required.",
        "The score reported here is measured on your data, not projected.",
        "Fully reproducible, debuggable and well understood operationally.",
    ],
    "hybrid": [
        "Keeps the reliability of a proven classical model in production.",
        "Lets a quantum sub-routine be evaluated in isolation, with a safe fallback.",
        "Builds quantum expertise before the hardware catches up with the algorithms.",
    ],
    "quantum": [
        "Explores a problem class where future hardware may eventually help.",
        "Builds in-house quantum capability ahead of the technology curve.",
    ],
}

LIMITATIONS = {
    "classical": [
        "May hit a performance ceiling that quantum approaches could one day break.",
        "Provides no insight into future hardware readiness.",
    ],
    "hybrid": [
        "Two toolchains to maintain, and a larger integration surface.",
        "The quantum sub-routine may add cost and latency without measurable benefit.",
        "End-to-end latency is higher than a purely classical pipeline.",
    ],
    "quantum": [
        "Not deployable at this data scale or feature dimensionality.",
        "Results would not be reproducible on current noisy devices.",
        "Substantially higher cost per experiment, with no guaranteed payoff.",
    ],
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _classical_quality(classical: dict[str, Any]) -> tuple[float | None, str]:
    """Measured classical quality on 0-1, with a human-readable description."""
    best = classical.get("best_model") or {}
    task = classical.get("task", "unknown")
    score = best.get("primary_score")
    if score is None:
        return None, "no model was trained"
    if task == "regression":
        return _clamp((float(score) + 1.0) / 2.0), f"R2 {float(score):.3f}"
    return _clamp(float(score)), f"{float(score) * 100:.1f}% {best.get('primary_metric') or 'score'}"


def _data_confidence(
    classical: dict[str, Any], problem: dict[str, Any], dataset: dict[str, Any]
) -> tuple[float, list[str]]:
    """How much the *inputs* can be trusted, independent of the verdict."""
    notes: list[str] = []
    parts: list[float] = []

    rows = int(dataset.get("rows") or 0)
    sample = _clamp(rows / 200.0) if rows else 0.0
    parts.append(sample)
    notes.append(
        f"{rows:,} rows available (sample adequacy {sample:.0%})."
    )

    missing = dataset.get("missing_percent")
    completeness = 1.0 if missing is None else _clamp(1.0 - (float(missing) / 40.0))
    parts.append(completeness)
    notes.append(f"{'unknown' if missing is None else str(missing) + '%'} missing cells.")

    target_ok = 1.0 if problem.get("target_column") else 0.4
    parts.append(target_ok)
    notes.append("Target column resolved." if target_ok == 1.0 else "No target column resolved.")

    trained = 1.0 if classical.get("status") == "completed" else 0.5
    parts.append(trained)
    notes.append(
        "A classical model was actually trained."
        if trained == 1.0
        else "No classical model was trained."
    )

    parts.append(float(problem.get("task_type_confidence") or 0.3))
    return round(sum(parts) / len(parts), 3), notes


def _confidence(
    approach_key: str,
    scores: dict[str, float],
    data_conf: float,
) -> float:
    """Confidence = decision margin + input quality, both made explicit."""
    ordered = sorted(scores.values(), reverse=True)
    margin = (ordered[0] - ordered[1]) / 100.0 if len(ordered) > 1 else 0.0
    # A decisive win is worth at most 0.4; a tie contributes nothing.
    value = 0.30 + 0.40 * _clamp(margin / 0.25) + 0.30 * data_conf
    return round(_clamp(value, 0.25, 0.95), 2)


def _label(confidence: float) -> str:
    if confidence >= 0.75:
        return "High confidence"
    if confidence >= 0.55:
        return "Moderate confidence"
    return "Low confidence"


def _decide(
    classical: dict[str, Any],
    quantum: dict[str, Any],
    problem: dict[str, Any],
    dataset: dict[str, Any],
    scores: dict[str, float],
) -> tuple[str, str, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Run the gates. Returns ``(approach_key, gate, reasons, gates, alternatives)``."""
    suitability = int(quantum.get("suitability_score") or 0)
    qubits = int(quantum.get("qubits_required") or 0)
    problem_type = problem.get("problem_type", "unknown")
    trained = classical.get("status") == "completed"
    quality, quality_text = _classical_quality(classical)
    rows_available = int(dataset.get("rows") or 0)
    methods = quantum.get("candidate_algorithms") or []
    clean_methods = [m for m in methods if not m.get("blocking_issues")]
    top_method = methods[0]["name"] if methods else "no quantum method"
    rows = int(dataset.get("rows") or 0)
    d = int((problem.get("characteristics") or {}).get("features") or 0)

    gates: list[dict[str, Any]] = []
    reasons: list[dict[str, Any]] = []
    alternatives: list[dict[str, Any]] = [
        {
            "approach": APPROACH_LABELS["classical"],
            "score": scores.get("classical"),
            "why_not": "Strong measured baseline and/or low quantum suitability.",
        },
        {
            "approach": APPROACH_LABELS["hybrid"],
            "score": scores.get("hybrid"),
            "why_not": "Requires a quantum sub-step with a plausible payoff.",
        },
        {
            "approach": APPROACH_LABELS["quantum"],
            "score": scores.get("quantum"),
            "why_not": f"Requires suitability >= {HIGH_SUITABILITY}, a register "
            f"<= {QUANTUM_QUBIT_BUDGET} qubits, at least {MIN_EXPERIMENT_ROWS} rows, "
            f"and either an optimisation task or a measured-but-weak classical result.",
        },
    ]

    # --- G2: low suitability, classical already measured -------------------
    if trained and suitability < LOW_SUITABILITY:
        gates.append({
            "gate": "G2",
            "name": "Low quantum suitability with a working classical baseline",
            "passed": True,
            "evidence": f"suitability {suitability}/100 < {LOW_SUITABILITY}, classical measured at {quality_text}",
        })
        reasons.append({
            "title": "Quantum methods are not a fit for this problem",
            "detail": (
                f"Quantum suitability scored {suitability}/100, below the "
                f"{LOW_SUITABILITY}/100 threshold at which Q-Compass considers "
                "quantum methods worth investigating."
            ),
            "impact": "High",
        })
        return "classical", "G2", reasons, gates, alternatives

    # --- G3: quantum, only if every gate condition is met ------------------
    # A classical result being *absent* is almost always a data problem (no
    # target, too few rows, an unparseable file) rather than evidence that
    # quantum would do better. Letting that satisfy G3 would recommend Quantum
    # AI for datasets we could not even analyse, so an absent baseline is only
    # acceptable alongside a genuine optimisation framing - and is never enough
    # on its own.
    classical_evidence = trained and quality is not None and quality < WEAK_CLASSICAL_QUALITY
    gate_conditions = {
        f"suitability >= {HIGH_SUITABILITY}": suitability >= HIGH_SUITABILITY,
        f"qubits <= {QUANTUM_QUBIT_BUDGET}": qubits <= QUANTUM_QUBIT_BUDGET,
        "optimisation task, or a measured-but-weak classical result": (
            problem_type == "optimization" or classical_evidence
        ),
        "dataset has enough rows to experiment on": rows_available >= MIN_EXPERIMENT_ROWS,
        "at least one method with no blocking issue": bool(clean_methods),
    }
    g3_detail = {k: v for k, v in gate_conditions.items()}
    gates.append({
        "gate": "G3",
        "name": "Quantum AI requires strong match AND feasibility",
        "passed": all(gate_conditions.values()),
        "evidence": g3_detail,
    })
    if all(gate_conditions.values()):
        failed = [k for k, v in gate_conditions.items() if not v]
        reasons.append({
            "title": "The problem clears every quantum gate",
            "detail": (
                f"Suitability {suitability}/100, register of {qubits} qubits, and "
                f"{top_method} has no blocking issue for this dataset."
            ),
            "impact": "High",
        })
        if failed:  # defensive: unreachable, kept so the logic stays honest
            logger.warning("G3 matched with failing conditions: %s", failed)
        return "quantum", "G3", reasons, gates, alternatives

    # --- G4: hybrid --------------------------------------------------------
    investigable = LOW_SUITABILITY <= suitability <= 85
    if investigable and (trained or quality is not None):
        sub_step = _pick_sub_step(methods, problem_type)
        gates.append({
            "gate": "G4",
            "name": "Hybrid: classical backbone plus an investigable quantum sub-step",
            "passed": True,
            "evidence": f"suitability {suitability}/100 in [30, 85]; sub-step = {sub_step}",
        })
        # The wording has to follow the measurement. Claiming the classical
        # model "handles it effectively" when it scored poorly would be exactly
        # the kind of unsupported claim this engine exists to avoid.
        baseline = classical.get("baseline_model") or {}
        floor_text = baseline.get("summary")
        if quality is not None and quality < WEAK_CLASSICAL_QUALITY:
            reasons.append({
                "title": "No approach performed well on this data",
                "detail": (
                    f"The best classical baseline scored only {quality_text}, and the "
                    f"trivial majority-class floor scored {floor_text or 'n/a'}. The "
                    "signal in this data is weak for every model tried, so the honest "
                    "first step is better features or a redefined label - not a "
                    "different computing paradigm."
                ),
                "impact": "High",
            })
        else:
            reasons.append({
                "title": "Classical ML handles the prediction effectively",
                "detail": (
                    f"{(classical.get('best_model') or {}).get('name', 'A classical model')} "
                    f"was measured at {quality_text} on this data, against a "
                    f"majority-class floor of {floor_text or 'n/a'}, so a classical "
                    "backbone is the safe production choice."
                ),
                "impact": "High",
            })
        reasons.append({
            "title": "A quantum sub-step is worth piloting",
            "detail": (
                f"Quantum suitability is {suitability}/100. The most promising angle is "
                f"{sub_step}, because the {d}-feature selection space has 2^{d} candidate "
                "subsets - a genuinely combinatorial sub-problem that a classical "
                "backbone can still score."
            ),
            "impact": "Medium",
        })
        reasons.append({
            "title": "No quantum end-to-end result exists yet",
            "detail": (
                "Current hardware is too noisy for a reliable end-to-end quantum model "
                "at this data scale, so a quantum-only pipeline is not defensible today."
            ),
            "impact": "High",
        })
        return "hybrid", "G4", reasons, gates, alternatives

    # --- G5: default -------------------------------------------------------
    gates.append({
        "gate": "G5",
        "name": "Default to classical",
        "passed": True,
        "evidence": f"suitability {suitability}/100, qubits {qubits}, task {problem_type}",
    })
    if not trained:
        reasons.append({
            "title": "No measured classical baseline was available",
            "detail": (
                "A classical model could not be trained on this dataset, so there is no "
                "evidence that a quantum approach would do better. Resolve the data "
                "issue first - a recommendation without a baseline is not a finding."
            ),
            "impact": "High",
        })
    else:
        reasons.append({
            "title": "The measured classical result is already strong",
            "detail": (
                f"{(classical.get('best_model') or {}).get('name')} reached {quality_text} "
                f"on {rows:,} rows, trained in "
                f"{(classical.get('best_model') or {}).get('training_time_sec')}s on CPU."
            ),
            "impact": "High",
        })
    return "classical", "G5", reasons, gates, alternatives


def _pick_sub_step(methods: list[dict[str, Any]], problem_type: str) -> str:
    """Name the most plausible quantum sub-step, preferring the top-ranked method."""
    if not methods:
        return "a quantum feature-selection step"
    if problem_type == "optimization":
        for method in methods:
            if "QAOA" in method["name"]:
                return "a QAOA-based search step"
    for method in methods:
        if "Feature Selection" in method["name"]:
            return "a quantum feature-selection step"
    return f"a pilot of {methods[0]['name']}"


def run(
    comparison: dict[str, Any],
    classical: dict[str, Any],
    quantum: dict[str, Any],
    problem: dict[str, Any],
    dataset: dict[str, Any],
    analysis_id: str = "",
) -> dict[str, Any]:
    """Produce the recommendation block from the actual analysis results."""
    scores = comparison.get("weighted_scores") or {}
    approach_key, gate, reasons, gates, alternatives = _decide(
        classical, quantum, problem, dataset, scores
    )
    data_conf, data_notes = _data_confidence(classical, problem, dataset)
    confidence = _confidence(approach_key, scores, data_conf)
    label = APPROACH_LABELS[approach_key]
    suitability = int(quantum.get("suitability_score") or 0)

    summary = _summary_for(approach_key, classical, quantum, problem, suitability, gate)
    next_steps = _next_steps(approach_key, quantum, classical)
    limitations = list(LIMITATIONS[approach_key]) + list(
        (quantum.get("limitations") or [])[:2]
    )

    return {
        # --- existing frontend contract (names unchanged) ---
        "recommended_approach": label,
        "approach_key": approach_key,
        "confidence": confidence,
        "confidence_label": _label(confidence),
        "headline": f"Recommended approach: {label}",
        "summary": summary,
        "scores": scores,
        "reasons": reasons,
        "advantages": list(BENEFITS[approach_key]),
        "limitations": limitations,
        "suggested_next_steps": next_steps,
        "roadmap": _roadmap(approach_key),
        "decision_basis": (
            f"Gate {gate} of the Q-Compass decision rules fired. Task type: "
            f"{problem.get('task_type')}. Quantum suitability {suitability}/100. "
            f"Classical status: {classical.get('status')}."
        ),
        "confidence_in_underlying_data": (
            f"Input-confidence {data_conf:.0%}. " + " ".join(data_notes)
        ),
        "is_mock": False,
        "disclaimer": (
            "This is a decision-support recommendation produced from a measured "
            "classical baseline and a transparent suitability model. It is not a "
            "claim of quantum advantage, and no quantum circuit was executed."
        ),
        # --- spec-shaped / transparency surface ---
        "approach": label,
        "reason_summaries": [r["detail"] for r in reasons],
        "gate": gate,
        "gates_evaluated": gates,
        "thresholds": {
            "low_suitability": LOW_SUITABILITY,
            "high_suitability": HIGH_SUITABILITY,
            "quantum_qubit_budget": QUANTUM_QUBIT_BUDGET,
            "weak_classical_quality": WEAK_CLASSICAL_QUALITY,
            "min_experiment_rows": MIN_EXPERIMENT_ROWS,
        },
        "alternatives_considered": alternatives,
        "input_confidence": data_conf,
        "input_confidence_notes": data_notes,
        "confidence_formula": (
            "confidence = 0.30 + 0.40 * clamp(margin / 0.25) + 0.30 * input_confidence, "
            "clamped to [0.25, 0.95], where margin is the gap between the top two "
            "weighted comparison scores."
        ),
    }


def _summary_for(
    approach_key: str,
    classical: dict[str, Any],
    quantum: dict[str, Any],
    problem: dict[str, Any],
    suitability: int,
    gate: str,
) -> str:
    best = (classical.get("best_model") or {}).get("name", "no classical model")
    primary = (classical.get("best_model") or {}).get("primary_metric", "score")
    value = (classical.get("best_model") or {}).get("primary_score")
    measured = f"{best} ({value:.3f} {primary})" if isinstance(value, float) else best
    task = problem.get("task_type", "Unknown")

    if approach_key == "classical":
        return (
            f"{task} on {int(problem.get('characteristics', {}).get('rows') or 0):,} rows. "
            f"A classical baseline was measured at {measured}, while quantum suitability "
            f"is only {suitability}/100. Classical AI is the defensible choice: the "
            f"evidence supports it and there is no demonstrated quantum alternative."
        )
    if approach_key == "quantum":
        return (
            f"{task} on {int(problem.get('characteristics', {}).get('rows') or 0):,} rows. "
            f"Quantum suitability is {suitability}/100 and the problem clears every "
            f"feasibility gate. Quantum AI is recommended as a research direction - "
            f"this is still not a claim that it will outperform classical ML."
        )
    return (
        f"{task} on {int(problem.get('characteristics', {}).get('rows') or 0):,} rows. "
        f"A classical backbone measured {measured} and quantum suitability is "
        f"{suitability}/100. Hybrid AI keeps the classical result in production while "
        f"piloting a quantum sub-step where the search space is genuinely combinatorial."
    )


def _next_steps(
    approach_key: str, quantum: dict[str, Any], classical: dict[str, Any]
) -> list[str]:
    methods = quantum.get("potential_methods") or []
    if approach_key == "classical":
        return [
            "Productionise the measured classical baseline and lock in its score as "
            "the acceptance floor.",
            "Reduce the feature space (correlation-based selection or PCA) and "
            "re-measure; a smaller d is the single change that would most improve "
            "future quantum feasibility.",
            "Re-run Q-Compass if the data scale or feature count changes materially - "
            "the suitability score is a function of both.",
        ]
    if approach_key == "quantum":
        return [
            "Prototype on a classical simulator first; do not request hardware until a "
            "simulator result is reproducible.",
            "Fix the classical baseline as the control arm so any quantum result has "
            "something to be compared against.",
            "Define the success criterion in advance, including the shot budget.",
        ]
    return [
        "Ship the classical model as the production path and keep it as the fallback.",
        f"Run a time-boxed simulator pilot of {methods[0] if methods else 'the top candidate'} "
        "on a reduced feature set.",
        "Pre-register the success criterion: the quantum step must beat the classical "
        "baseline on a held-out split, or be discarded.",
        "Re-run the comparison once the pilot produces measured numbers instead of a "
        "suitability score.",
    ]


def _roadmap(approach_key: str) -> list[dict[str, str]]:
    if approach_key == "classical":
        return [
            {"phase": "Phase 1", "title": "Lock in the classical baseline", "status": "in-progress"},
            {"phase": "Phase 2", "title": "Reduce the feature space", "status": "not-started"},
            {"phase": "Phase 3", "title": "Re-assess quantum feasibility", "status": "blocked"},
        ]
    if approach_key == "quantum":
        return [
            {"phase": "Phase 1", "title": "Establish the classical control", "status": "in-progress"},
            {"phase": "Phase 2", "title": "Simulator pilot", "status": "not-started"},
            {"phase": "Phase 3", "title": "Compare measured results", "status": "blocked"},
            {"phase": "Phase 4", "title": "Hardware evaluation", "status": "blocked"},
        ]
    return [
        {"phase": "Phase 1", "title": "Ship the classical backbone", "status": "in-progress"},
        {"phase": "Phase 2", "title": "Pilot the quantum sub-step", "status": "not-started"},
        {"phase": "Phase 3", "title": "Compare measured results", "status": "blocked"},
        {"phase": "Phase 4", "title": "Production decision", "status": "blocked"},
    ]
