# Q-Compass Analysis Engine

The intelligence behind Q-Compass: it reads a dataset and a problem statement,
and decides whether the problem is better served by **Classical AI**, **Quantum
AI**, or a **Hybrid** approach.

> **The governing principle**
>
> *Use quantum computing only when the problem characteristics justify
> investigating it.*
>
> This engine is a decision-support tool, not an advocate. The default answer is
> Classical AI, and Quantum AI has to earn its way out. Nothing in this codebase
> fabricates a quantum speedup, a quantum accuracy, a hardware capability, or an
> experimental result.

---

## Table of contents

- [Pipeline](#pipeline)
- [1. Dataset profiling](#1-dataset-profiling)
- [2. Problem characterization](#2-problem-characterization)
- [3. Classical baseline](#3-classical-baseline)
- [4-5. Quantum suitability](#4-5-quantum-suitability-scoring)
- [6. Comparison](#6-comparison)
- [7. Recommendation](#7-recommendation-engine)
- [Response shape](#response-shape)
- [Error handling](#error-handling)
- [Configuration](#configuration)
- [Limitations](#limitations)
- [Plugging in real quantum algorithms](#plugging-in-real-quantum-algorithms)
- [Tests](#tests)

---

## Pipeline

```
POST /api/upload  ->  dataset_service.build_dataset()      # parse + profile
POST /api/analyze -> problem_service.build_problem()       # characterise
                     classical_service.run()                # train + measure
                     quantum_service.run()                  # score suitability
                     comparison_service.run()               # weighted matrix
                     recommendation_service.run()           # decision rules
                     report_service.run()                   # render
```

Each stage is a standalone module with a single entry point. Stages never import
each other; the orchestrator (`analysis_service.py`) owns the order and hands each
stage the DataFrame it needs.

`utils/dataset_cache.py` holds the single parse of the uploaded file, so a
20k-row XLSX is read once rather than once per stage.

---

## 1. Dataset profiling

`dataset_service.py` + `utils/profiling.py`

Parses CSV, XLSX and JSON into a DataFrame with **pandas**, then measures it.

| Measured | Notes |
|---|---|
| Rows, columns | After dropping fully-empty columns |
| Numerical / categorical / datetime features | By pandas dtype (bool counts as categorical) |
| Missing values | Absolute count and % of cells, plus how many columns are affected |
| Duplicate rows | Exact row duplicates, count and % |
| Class distribution | Full label counts for a detected target |
| Target column | User-specified, else a column-name heuristic |
| Feature cardinality | Distinct values per column (sampled to 5,000 rows) |
| High-cardinality / id-like features | Ratio- and uniqueness-based |
| Feature-to-sample ratio | `d / n` |
| Approximate dimensionality | Feature count, and `log2(2**d) = d` as the selection-space size |
| Dataset size | On disk (MB) and in memory after parsing |

**Formats.** CSV (delimiter auto-detected), XLSX via `openpyxl`, and JSON in all
three shapes seen in practice - a list of records, `{"data": [...]}`, or
newline-delimited JSON.

**Delimiter detection.** A CSV's delimiter is *never* assumed. `csv.Sniffer` gets
a first vote, and a counting heuristic ranks the rest by how consistently a
candidate appears across the first 20 lines. Every candidate is then actually
parsed and the best result wins (most columns, then most rows, then most numeric
columns). Supported: comma `,`, semicolon `;`, tab `\t`, pipe `|`.

This matters because the **UCI Wine Quality files are semicolon-delimited**. A
comma read collapses each row into one column, which previously surfaced as
"the dataset has fewer than two columns". Non-comma delimiters are also retried
with a `,` decimal separator, the usual companion of European exports.

If every delimiter still yields a single column the file is **rejected with an
actionable message** naming all supported delimiters - the validation is kept,
just moved after exhaustive detection. Each parse is logged:

```
CSV parsed: delimiter=semicolon (;) decimal='.' rows=4908 columns=12 numeric_columns=12
```

**Headerless CSVs.** Some well-known files ship with no header line (for example
UCI `bezdekIris.csv`). A naive read treats row 1 as a header, which silently
destroys a data row and turns the label column into a column *name* - after which
no target can be found and the supervised stages are skipped. When most column
names parse as numbers, the file is re-read with `header=None` and the columns
are named deterministically: a **non-numeric final column** with numeric columns
before it becomes `feature_1 .. feature_{n-1}` + `target` (so the normal
exact-name target heuristic resolves it); anything else becomes `column_1 ..
column_n`.

**Data-quality findings are never fatal.** Duplicate rows, missing values and
high-cardinality columns are reported as warnings with their counts and
percentages intact, and the pipeline always continues. Only genuinely
unusable input stops a stage: an empty file, an unreadable one, zero usable
columns, or too little data to evaluate.

**Target detection.** `_TARGET_HINTS` prefers exact names (`target`, `label`,
`class`, `y`, `outcome`, `result`) then prefixes (`is_`, `has_`, `churn`,
`fraud`, ...). A caller can always override it with the `target_column` form
field or request field; an unknown name is logged and falls back to the
heuristic rather than failing.

**Row budget.** At most `ANALYSIS_MAX_ROWS` rows are read. Larger files are
sampled head+tail (deterministic, so repeated runs match) and flagged
`sampled: true` with an explicit warning that the statistics describe the
sample.

**A categorical target is always classification**, including the degenerate
single-class case. A one-class label is a classification problem that cannot be
*evaluated* — sending it to a regressor would be a category error.

---

## 2. Problem characterization

`problem_service.py`

Returns one of: `classification`, `regression`, `clustering`, `optimization`,
`unknown`.

**Two signals, deliberately ordered.** Structural evidence from the target
column is decisive; the problem statement disambiguates. The one exception is an
**optimisation framing**, which has no structural signature at all (no dataset
looks like a scheduler), so the text is authoritative for it — and requires at
least two distinct optimisation cues so a passing mention of "search" cannot
hijack a plain prediction task.

A user writing "regression" in the prompt cannot turn a 2-class label into a
regression task.

**Characteristics** (all measured, all reported):
`rows`, `features`, `feature_to_sample_ratio`, `num_classes`, `class_imbalance`
(majority share, imbalance ratio, severity), `sparsity` (share of zero/empty
cells), `redundancy` (count of feature pairs with |Pearson r| >= 0.95),
`estimated_search_space`, `memory_footprint_mb`, plus the evidence trail in
`detection.signals`.

---

## 3. Classical baseline

`classical_service.py` — the only stage that trains a model.

| Task | Candidates (best first) | Primary metric |
|---|---|---|
| Classification | Logistic Regression, Random Forest, SVM (RBF), Dummy (majority) | macro-F1 |
| Regression | Linear Regression, Random Forest Regressor, Dummy (mean) | R² |

**Every candidate is trained and measured on a real 20% hold-out split.** A
single estimator failing is reported (`suitable: false` + reason) and never
takes down the stage.

**Why the Dummy model is trained too.** "How much of this 0.98 accuracy is just
the majority class?" is the first question a reader should ask. The dummy
baseline answers it, and the engine warns when the best model barely beats it.

**Metrics.** Classification reports accuracy, macro-F1, macro-precision and
macro-recall. *Macro* averaging is used deliberately: it is defined for any
number of classes, weights each class equally, and does not need a `pos_label`
when labels are strings rather than 0/1. Regression reports MAE, RMSE and R².
(`root_mean_squared_error` is used because scikit-learn removed the
`squared=False` argument.)

**Preprocessing.** Numeric: median imputation + standardisation. Categorical:
most-frequent imputation + one-hot with `min_frequency=2` so a high-cardinality
column cannot explode the design matrix.

**Budgets** (all in `config.py`): `ANALYSIS_MAX_TRAIN_ROWS`, a small forest
(`ANALYSIS_FOREST_TREES`, capped depth), and the SVM is skipped entirely above
`ANALYSIS_SVM_MAX_ROWS` features/rows because it is `O(n²·d)`.

**When it is skipped, and why.** `status: "skipped"` with a plain-English
`summary` when: the problem is not supervised, no target could be resolved, the
data could not be loaded, there are fewer than 10 usable rows, the target has one
class, the rarest class has fewer than 2 samples, or a split was impossible.

---

## 4-5. Quantum suitability scoring

`quantum_service.py`

### What the score means

| | |
|---|---|
| **Means** | "How suitable is this problem for *investigating* quantum methods?" |
| **Does NOT mean** | "Quantum will outperform classical AI here." |

That distinction is not just documentation — it is in the payload
(`score_interpretation`), it is asserted by the test suite, and it is enforced
structurally: **no circuit is ever built or executed**, so there is no
performance figure to over-claim in the first place.

### The formula

```
raw   = sum( weight_i * factor_i )        for i = 1..6,   sum(weight_i) = 1.0
score = round(100 * min(raw, 1.0)), then hard caps are applied
```

| # | Factor | Weight | Normalised from |
|---|---|---|---|
| 1 | `optimization_suitability` | 0.20 | Problem framing. 1.0 optimisation task; 0.8 if the statement carries an optimisation cue; 0.45 predictive task (a feature-selection sub-problem exists); 0.35 clustering; 0.15 otherwise. |
| 2 | `search_space_complexity` | 0.20 | `min(d / 64)`. The feature-selection space has `2**d` members, so `log2 = d`. |
| 3 | `feature_dimensionality` | 0.12 | 1.0 for `d <= 8`, linear decay to 0 at `d = 64`. Angle encoding needs one qubit per feature. |
| 4 | `dataset_size_compatibility` | 0.18 | 1.0 for `n <= 500`, then linear on a log scale to 0 at `n = 10,000`. Shot-based training cost scales with sample count. |
| 5 | `encoding_feasibility` | 0.15 | Starts at 1.0; penalties for one-hot cardinality blow-up, identifier-like/free-text *categorical* columns, and missing data. |
| 6 | `hardware_feasibility` | 0.15 | `1 - qubits / 127`, clamped to `[0, 1]`. |

Factor 5 penalises **categorical** cardinality only. A continuous column has a
distinct value per row by nature and angle encoding handles it perfectly; counting
that as an encoding problem would penalise healthy numeric data.

### Hard caps

A weighted average is too forgiving of a single disqualifying fact, so:

* **qubits required > 127** (the reference budget) → capped at **25**
* **predictive task (`classification`/`regression`) with `d > 64`** → capped at **35**

Caps are reported in `scoring.caps_applied` with the reason, and appear in the
reasoning list. The assertion `sum(weights) == 1.0` runs at import, and
`tests/test_scoring.py` re-derives the score from the published formula so the
documentation cannot drift from the code.

### The whole factor table is returned

```jsonc
"scoring": {
  "formula": "score = 100 * min(1, sum(weight_i * factor_i)), then hard caps",
  "factors": [
    { "key": "search_space_complexity", "raw_value": "d = 48",
      "normalised": 0.75, "weight": 0.2, "contribution": 0.15,
      "explanation": "Selecting a subset of 48 features means searching 48 bits of solution space (2^48 candidate subsets)." }
  ],
  "raw_score": 75.7,
  "caps_applied": []
}
```

### Qubit estimation

All three standard encodings are reported, because the choice of encoding is the
single biggest driver of feasibility:

| Encoding | Qubits | Note |
|---|---|---|
| Angle | `d` | 1 per feature, no state preparation |
| One-hot | `sum(cardinality)` over categorical **input** columns | Blows up fast |
| Amplitude | `ceil(log2 d)` | Looks tiny; needs ~`max(0, 2**n - d)` swap gates of state preparation (Nielsen & Chuang) |

The *recommended* encoding is the cheapest **credible** one, not simply the
smallest number: amplitude encoding is only recommended while `d <= 8` and its
state-prep cost stays under 16 gates. The target column is excluded from encoding
cost entirely — a 2-level label must not make a dataset look cheap to encode.

### Candidate methods

Ranked by a transparent relevance score (not a predicted accuracy):
**Quantum Feature Selection** (the strongest generic candidate, since `2**d` really
is combinatorial), **QAOA** (only when the task is an optimisation),
**VQC**, and **Quantum Kernel (QSVM)**. Each entry carries `blocking_issues`,
which gate G3 checks.

### Execution honesty

```jsonc
"execution": {
  "mode": "theoretical-suitability-analysis",
  "framework": null,              // "qiskit" / "pennylane" if installed
  "framework_available": false,
  "hardware_executed": false,     // always false, by construction
  "statement": "No quantum circuit was executed. ..."
}
```

---

## 6. Comparison

`comparison_service.py`

Eight weighted criteria, each scored 0-100 per approach. Weights live in
`CRITERION_WEIGHTS` and are exported, so the weighting can be re-derived or
replaced without touching the scoring code.

| Criterion | Weight |
|---|---|
| Accuracy / Precision | 0.30 |
| Computational Complexity | 0.15 |
| Training Time | 0.15 |
| Scalability | 0.10 |
| Hardware Requirements | 0.10 |
| Data Size Suitability | 0.10 |
| Optimisation Potential | 0.05 |
| Quantum Feasibility (today) | 0.05 |

**Every cell carries a `basis` tag** so a reader can tell a measurement from a
modelling choice:

* `measured` — computed from a real training run or a real dataset property.
* `derived` — a deterministic function of a measured value (e.g. cost class,
  qubit budget).
* `assumption` — a deliberate modelling choice, e.g. "a hybrid pipeline keeps
  the classical accuracy minus 2 points, because the quantum step's effect on it
  is unknown and may be zero or negative."

**The accuracy row never claims a quantum accuracy.** The quantum cell on
"Accuracy / Precision" is scored as *experimental readiness* — how likely it is
that any credible quantum number could be produced at all — with the value
literally set to `"Not measured"`, `basis: "assumption"`, and a note saying so.
`comparison.approaches.quantum.measured_performance` is `null`.

---

## 7. Recommendation engine

`recommendation_service.py`

This is **not** a vote on the weighted comparison. It applies an ordered set of
gates and returns the first that matches, along with the evidence that matched
it. Quantum AI must clear every condition in G3.

| Gate | Condition | Result |
|---|---|---|
| **G2** | classical measured **and** suitability < 30 | Classical |
| **G3** | suitability >= 70 **and** qubits <= 32 **and** (optimisation task **or** weak/absent classical result) **and** >= 1 method with no blocking issue | Quantum |
| **G4** | classical backbone exists **and** suitability in [30, 85] **and** a concrete quantum sub-step | Hybrid |
| **G5** | otherwise | Classical |

Thresholds live in module constants (`LOW_SUITABILITY`, `HIGH_SUITABILITY`,
`QUANTUM_QUBIT_BUDGET`, `WEAK_CLASSICAL_QUALITY`) and are echoed in the response
under `recommendation.thresholds`.

**G3 is deliberately hard to pass, and in the current hardware landscape it is
expected to fail.** That is the correct outcome. The rules are written to change
as evidence accumulates — not to reach a predetermined answer.

**Confidence** is a transparent formula, returned in the payload:

```
confidence = 0.30
           + 0.40 * clamp(margin / 0.25)      # margin = top1 - top2 score gap
           + 0.30 * input_confidence          # rows, completeness, target, baseline
           clamped to [0.25, 0.95]
```

`input_confidence` averages sample adequacy, data completeness, whether a target
was resolved, whether a model was actually trained, and the task-type
confidence — so a verdict built on thin evidence reports low confidence.

**Transparency fields:** `gate`, `gates_evaluated` (with evidence and pass/fail),
`alternatives_considered` (with *why not*), `thresholds`, `input_confidence_notes`,
and `confidence_formula`.

---

## Response shape

`POST /api/analyze` returns:

```jsonc
{
  "analysis_id": "an_...", "status": "completed",
  "data_source": "real", "mock_data": false,
  "pipeline": [ /* 7 stages, all completed */ ],
  "warnings": [ /* flattened, de-duplicated */ ],

  "dataset":             { /* profiling, §1 */ },
  "problem":             { /* characterisation, §2 */ },
  "classical_analysis":  { /* measured baselines, §3 */ },
  "quantum_analysis":    { /* suitability + factor table, §4-5 */ },
  "comparison":          { /* weighted matrix, §6 */ },
  "recommendation":      { /* verdict + gates + reasoning, §7 */ },
  "report":              { /* structured sections + Markdown */ }
}
```

Every block additionally carries `is_mock: false` and a `note` describing where
its numbers came from.

---

## Error handling

`utils/errors.py` defines one exception class per failure mode, each carrying an
HTTP status and a user-safe message. `main.py` registers a single handler, so
"return a useful error instead of crashing" is a structural property.

| Condition | Error | Status |
|---|---|---|
| Unsupported file type | `UnsupportedFileTypeError` | 415 |
| Empty upload / header-only file | `EmptyDatasetError` | 422 |
| Unparseable content | `ParseError` | 422 |
| Dataset too large | `DatasetTooLargeError` | 413 |
| Missing target | `MissingTargetError` | 422 |
| Non-numeric where numeric required | `NonNumericDataError` | 422 |
| Too few samples / classes | `InsufficientSamplesError` | 422 |
| Model training failure | `ModelTrainingError` | 500 |
| Invalid problem description | `InvalidProblemDescriptionError` | 422 |
| Quantum framework required but absent | `QuantumLibraryUnavailableError` | 503 |

**Degradation, not failure.** A dataset that cannot be parsed still returns a
complete payload: `dataset.parse_error` explains what happened, the downstream
stages return `status: "skipped"` with a reason, and the recommendation is still
produced. A partial report beats a 500.

**Stage isolation.** `analysis_service._safe()` catches *unexpected* exceptions
so one broken stage cannot take down the run. Typed `AnalysisError`s are
deliberately **not** caught there: they are user-facing conditions that already
carry the right status code, and hiding them behind a 200 would mask a real
problem.

---

## Configuration

Every budget is an environment-driven setting in `config.py` (see
`backend/.env.example`). The ones that change engine behaviour:

| Setting | Default | Effect |
|---|---|---|
| `ANALYSIS_MAX_ROWS` | 20000 | Rows read from disk; larger files are sampled |
| `ANALYSIS_MAX_TRAIN_ROWS` | 20000 | Rows used for fitting |
| `ANALYSIS_FOREST_TREES` / `_MAX_DEPTH` | 200 / 12 | Random-forest budget |
| `ANALYSIS_CV_FOLDS` | 3 | Cross-validation folds |
| `ANALYSIS_SVM_MAX_ROWS` / `_MAX_FEATURES` | 5000 / 200 | Above this the O(n^2 d) SVM is skipped |
| `ANALYSIS_RANDOM_SEED` | 42 | Every sampler and estimator, so runs are reproducible |
| `QUANTUM_REFERENCE_QUBITS` | 127 | Hardware-feasibility denominator |
| `QUANTUM_ENCODING_FEATURE_CEILING` | 64 | Above this, angle encoding is out of reach |
| `QUANTUM_SAMPLE_CEILING` | 10000 | Above this, shot-based training is out of reach |

---

## Limitations

Be clear about what this engine is and is not.

1. **No quantum result exists.** No circuit is built or executed. Every quantum
   number is an analytical estimate of *suitability*, not performance.
2. **The suitability score is a prioritisation heuristic, not a physical model.**
   Its weights are defensible and fully disclosed, but they are a judgement call,
   and the hard caps are policy rather than physics.
3. **The reference qubit budget is a published capability figure**, not a
   measurement of any particular device, and it ignores connectivity, error rates
   and queue times.
4. **The classical baseline is a baseline, not a best result.** Models are cheap
   and untuned on purpose. A well-tuned ensemble will beat them.
5. **Rows are sampled above the budget.** Statistics on a large file describe
   the head and tail of it, and the payload says so.
6. **The task-type heuristic is keyword-based.** It is deliberately overridden by
   structural evidence, and an optimisation framing still depends on how the user
   words their problem.
7. **In-memory storage.** Analyses are lost on restart and not shared between
   workers (`utils/store.py` is the seam for a real database).
8. **No authentication, rate limiting, or upload retention policy.**
9. **The report is Markdown only.**

---

## Plugging in real quantum algorithms

The engine is deliberately modular so that a real experiment can be added
without rewriting anything — and, critically, so that a future experiment can
*contradict* the current recommendation and be shown doing so.

### 1. Add an experiment module

Create `services/quantum_experiments/` with one module per hypothesis, e.g.
`qaoa_feature_selection.py`:

```python
def run(frame, target, problem, *, shots: int = 4096) -> dict:
    """Run one real experiment. Return measured values only."""
    from qiskit import QuantumCircuit          # imported lazily, on purpose
    from qiskit_aer import AerSimulator

    circuit = build_feature_selection_circuit(n_features=frame.shape[1], layers=2)
    backend = AerSimulator()
    counts = backend.run(circuit, shots=shots).result().get_counts()
    accuracy = score(counts, y_true=target)   # measured, not assumed
    return {
        "method": "QAOA feature selection",
        "shots": shots,
        "accuracy": accuracy,                  # a MEASUREMENT
        "seconds": elapsed,
        "backend": "aer_simulator",
    }
```

Rules for anything added here:

* **Return only what you measured.** If you did not run it, do not report it.
* **Keep the import lazy.** A missing framework must degrade to
  `QuantumLibraryUnavailableError`, never break the app.
* **Always run the classical control** in the same run, so the quantum number
  has something to be compared against.
* **Label the execution mode** in the result: `"simulated"`,
  `"hardware"`, or `"theoretical"`. Never blur them.

### 2. Report it honestly

```python
"execution": {
  "mode": "simulated",           # NOT "theoretical-suitability-analysis"
  "framework": "qiskit",
  "hardware_executed": false,
  "statement": "QAOA feature selection was executed on the Aer simulator with
                4096 shots over 5 random restarts."
}
```

### 3. Let the data change the recommendation

A measured experiment that beats the classical baseline is the only thing that
should ever move a verdict toward Quantum AI. Add an explicit gate — do not
rely on the suitability heuristic for it:

```python
# In recommendation_service._decide, as a new gate before G4:
if experiment and experiment["accuracy"] > classical["best_model"]["primary_score"]:
    return "quantum", "G2.5", ...
```

### 4. Keep the simulator/hardware distinction visible

`available_framework()` already reports whether Qiskit or PennyLane is
installed. `hardware_executed` is `False` by construction today and must stay
`False` unless a real device was actually used. If a result ever comes back from
a simulator, it says so; if it ever comes back from hardware, it says that too.

---

## Tests

```bash
cd backend
pytest              # 54 tests
pytest -v tests/test_scenarios.py
```

| File | Covers |
|---|---|
| `tests/conftest.py` | The three specified datasets, generated deterministically |
| `tests/test_scenarios.py` | The three required scenarios, outcome **and** reasoning |
| `tests/test_errors.py` | Every error path in the table above |
| `tests/test_api_contract.py` | Every key the React pages read still exists and is usable |
| `tests/test_scoring.py` | The formula, reproducibility, monotonicity, caps, bounds |

The three specified scenarios:

1. **Small classification** → classical baseline is trained, beats the
   majority-class floor, is reported as `High` feasibility, and is what gets
   recommended.
2. **High-dimensional feature selection** (48 features, only every 6th
   informative) → *Quantum Feature Selection* is the top candidate, the
   search-space factor does real work, and the accuracy row still refuses to
   claim a quantum number.
3. **Optimisation framing** (no target column at all) → the task type comes from
   the statement, *QAOA* is the top candidate, and no predictive model is
   invented.
