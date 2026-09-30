# Q-Compass — Quantum Readiness & AI Decision Engine

> **What the analysis does.** Q-Compass profiles your dataset, characterises the
> ML problem, **trains real classical baselines and reports what they actually
> scored**, scores **quantum suitability** from transparent factors, and
> recommends Classical, Hybrid or Quantum AI via explicit decision rules.
>
> **What it does not do.** It never claims a quantum advantage. The quantum
> stage runs on a **local simulator**, never on quantum hardware, and no
> hardware performance is fabricated. **Classical AI is the default** —
> Quantum AI has to earn its way out.
>
> Full engine documentation: **[`backend/services/README.md`](backend/services/README.md)**.

Q-Compass analyses an AI/ML problem and helps decide whether it is better suited
to **Classical AI**, **Quantum AI**, or a **Hybrid** approach.

---

## Table of contents

- [Project overview](#project-overview)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Folder structure](#folder-structure)
- [Frontend setup](#frontend-setup)
- [Backend setup](#backend-setup)
- [How to run](#how-to-run)
- [API endpoints](#api-endpoints)
- [What is real vs. modelled](#what-is-real-vs-modelled)
- [Current limitations](#current-limitations)
- [Future implementation plan](#future-implementation-plan)

---

## Project overview

The prototype flow is exactly:

```
Q-Compass
   ↓
Dashboard
   ↓
Upload Dataset
   ↓
Dataset & Problem Analysis
   ↓
Classical Analysis
   ↓
Quantum Analysis
   ↓
Classical vs Quantum Comparison
   ↓
Recommendation
   ↓
Detailed Report
```

Every page and every transition works today, and every value on them comes from
the analysis engine: measured classical scores, a transparent quantum suitability
score with its full factor breakdown, and a recommendation that names the
decision gate which fired.

### Pipeline stages

| # | Stage | Route | Status |
|---|-------|-------|--------|
| 1 | Dataset uploaded | `/upload` | **Real** (parse + profile) |
| 2 | Dataset & problem analysis | `/analysis` | **Real** (structure + task characterisation) |
| 3 | Classical analysis | `/classical` | **Real** (models trained, metrics measured) |
| 4 | Quantum analysis | `/quantum` | **Real** (QAOA circuit executed on a local Qiskit Aer simulator) |
| 5 | Comparison | `/comparison` | **Real** (derived from measured inputs) |
| 6 | Recommendation | `/recommendation` | **Real** (decision rules) |
| 7 | Report generation | `/report` | **Real** (Markdown export) |

The payload contract is unchanged, so no frontend rework was needed to swap the
mock engine for the real one.

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 19, Vite 6, React Router 6, plain CSS (design tokens) |
| Backend | Python 3.13, FastAPI, Pydantic v2, Uvicorn |
| Database | None yet — behind a repository protocol (see [Architecture](#architecture)) |
| Charts | Dependency-free inline SVG components |

No UI framework, no chart library, no state-management library — deliberately
kept lean so the team can swap in real engines without fighting the stack.


---

## Architecture

### The decoupling rule

Every pipeline stage is a separate service module with a single `run(...)`
function. Stages never import each other — they only read the shared context
object. That is what makes the "plug in real intelligence later" requirement
achievable without a rewrite.

```
upload → profiling → classical → quantum → comparison → recommendation → report
                                   ▲
                    (each stage is independently replaceable)
```

```
   browser ─► routes/ ─► orchestrator ─► dataset | classical | quantum |
                                            comparison | recommendation | report
                                                    │
                                          services/*  (the engine)
                                                    │
                                            utils/store.py  (DB seam)
```

### Where the engines live

| Concern | File | What it does |
|---|---|---|
| Dataset parsing / profiling | `utils/profiling.py` | pandas reader + full structural profile |
| Ingest + dataset block | `services/dataset_service.py` | validate, store, parse once, cache the frame |
| Problem classification | `services/problem_service.py` | task type + measured characteristics |
| Classical benchmarking | `services/classical_service.py` | trains scikit-learn models, reports measured metrics |
| Quantum suitability | `services/quantum_service.py` | 5-factor transparent scoring over the executed circuit |
| Quantum *experiment* | `services/quantum_service.py` | builds a p=1 QAOA Max-Cut graph from feature correlations and runs it on a local Qiskit Aer simulator |
| Comparison scoring | `services/comparison_service.py` | weighted matrix with per-cell `basis` tags |
| Recommendation | `services/recommendation_service.py` | ordered decision gates (G2–G5) |
| Report | `services/report_service.py` | structured sections + Markdown |
| Persistence | `utils/store.py` | implement `AnalysisRepository` for a real database |

The payload contract is fixed, so the frontend needed **no structural changes**
when the mock engine was replaced:

```jsonc
{
  "analysis_id": "an_77d9226d4ad5",
  "status": "completed",
  "data_source": "real",
  "mock_data": false,
  "warnings": [ ],
  "dataset":             { },     // stage 2
  "problem":             { },     // stage 2
  "classical_analysis":  { },     // stage 3  (measured)
  "quantum_analysis":    { },     // stage 4  (scored, not executed)
  "comparison":          { },     // stage 5
  "recommendation":      { },     // stage 6
  "report":              { }      // stage 7
}
```

---

## Folder structure

```
ramaiah/
├── README.md
├── .gitignore
├── samples/
│   └── customer_churn_sample.csv     # demo dataset (500 rows, 10 cols)
├── backend/
│   ├── main.py                       # FastAPI app factory, CORS, routers
│   ├── config.py                     # env-driven settings
│   ├── requirements.txt
│   ├── .env.example
│   ├── routes/
│   │   ├── health.py                 # /api/health, /api/meta
│   │   ├── upload.py                 # /api/upload
│   │   └── analysis.py               # /api/analyze, /api/analysis/*
│   ├── services/                     # THE ANALYSIS ENGINE
│   │   ├── README.md                 # <- full engine documentation
│   │   ├── analysis_service.py       # orchestrator (owns stage order)
│   │   ├── dataset_service.py        # stage 1  ingest + profile
│   │   ├── problem_service.py        # stage 2  problem characterisation
│   │   ├── classical_service.py      # stage 3  trains + measures models
│   │   ├── quantum_service.py        # stage 4  suitability scoring
│   │   ├── comparison_service.py     # stage 5  weighted matrix
│   │   ├── recommendation_service.py # stage 6  decision gates
│   │   └── report_service.py         # stage 7  sections + Markdown
│   ├── models/
│   │   ├── schemas.py                # Pydantic request/response contracts
│   │   └── mock/pipeline.py          # static stage defs for the UI stepper
│   └── utils/
│       ├── store.py                  # database seam (AnalysisRepository)
│       ├── profiling.py              # pandas reader + structural profiler
│       ├── dataset_cache.py          # parse each upload exactly once
│       ├── errors.py                 # typed errors -> HTTP status codes
│       ├── file_utils.py             # upload validation, path-traversal guard
│       ├── ids.py  formatting.py  logging_config.py
│   ├── uploads/                      # .gitkeep only
│   ├── tests/                        # 54 tests (pytest)
│   └── pytest.ini
└── frontend/
    ├── package.json  vite.config.js  eslint.config.js  index.html
    ├── .env.example
    ├── public/favicon.svg
    └── src/
        ├── main.jsx                  # entry
        ├── App.jsx                   # routes
        ├── components/
        │   ├── ui/index.jsx          # Card, Button, Badge, Alert, states
        │   ├── charts/index.jsx      # BarChart, RadarChart, ColumnChart, ScoreGauge
        │   ├── layout/               # AppLayout, Sidebar, Topbar
        │   ├── PageHeader.jsx
        │   ├── PipelineStepper.jsx
        │   └── RequireAnalysis.jsx   # flow guard
        ├── pages/                    # one file per route
        │   ├── Dashboard.jsx  UploadDataset.jsx  ProblemAnalysis.jsx
        │   ├── ClassicalAnalysis.jsx  QuantumAnalysis.jsx  Comparison.jsx
        │   ├── Recommendation.jsx  DetailedReport.jsx  NotFound.jsx
        ├── context/AnalysisContext.jsx  # shared analysis state
        ├── hooks/useAsync.js  useApiHealth.js
        ├── services/api.js           # the only place fetch() is called
        ├── constants/navigation.js
        ├── utils/format.js
        └── styles/                   # tokens, base, shell, components, patterns
```

---

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env      # optional — see below
npm run dev               # http://localhost:5173
```

Other scripts:

```bash
npm run build             # production build to dist/
npm run preview           # serve the production build
npm run lint              # eslint
```

**Configuration.** Leave `VITE_API_URL` empty in development — Vite proxies
`/api` to `http://127.0.0.1:8000` (see `vite.config.js`), so the browser stays
same-origin and CORS is never involved. Set `VITE_API_URL=https://api.example.com`
only when the API is deployed separately.

> Vite binds to `localhost`, which resolves to IPv6 (`::1`) on Windows. If
> `http://127.0.0.1:5173` is refused, use `http://localhost:5173` — or run
> `npm run dev -- --host` to bind all interfaces.

---

## Backend setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env      # optional — defaults work out of the box
uvicorn main:app --reload --port 8000
```

The API is then on <http://127.0.0.1:8000>, with interactive docs at
<http://127.0.0.1:8000/docs>.

**Configuration** (all optional, see `backend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |
| `UPLOAD_DIR` | `uploads` | Where uploaded datasets are written |
| `MAX_UPLOAD_BYTES` | `26214400` (25 MB) | Upload size limit |
| `STORE_MAX_ITEMS` | `50` | Analyses kept in the in-memory store |
| `ENVIRONMENT` | `development` | Free-form environment label |
| `ANALYSIS_MAX_ROWS` | `20000` | Rows read from disk; larger files are sampled |
| `ANALYSIS_RANDOM_SEED` | `42` | Every sampler and estimator, so runs reproduce |
| `QUANTUM_REFERENCE_QUBITS` | `127` | Hardware-feasibility denominator |

See [`backend/services/README.md`](backend/services/README.md#configuration) for
the full list of engine budgets.

---

## How to run

Two terminals.

**Terminal 1 — backend**

```bash
cd backend
.venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — frontend**

```bash
cd frontend
npm install
npm run dev
```

Then open **<http://localhost:5173>**.

### Walking the demo

1. **Dashboard** — overview, approach readiness cards, recent analyses.
2. **Upload Dataset** — pick `samples/customer_churn_sample.csv`, type
   *“Predict customer churn using historical customer data.”*, press
   **Upload Dataset**, then **Start Analysis**.
3. **Problem Analysis** — real row/column counts, feature types, missing values
   and the auto-detected `is_churned` target column.
4. **Classical Analysis** — Logistic Regression, Random Forest and an RBF SVM are
   trained on an 80% split and scored on a held-out 20%, alongside a
   majority-class baseline.
5. **Quantum Analysis** — the suitability score, the full factor breakdown behind
   it, the qubit estimate, and candidate methods with their blocking issues.
6. **Comparison / Recommendation / Report** — the weighted matrix, the decision
   gate that fired and why, and a downloadable Markdown report.

Production build:

```bash
cd frontend && npm run build && npm run preview
```

---

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness probe (used by the UI status pill) |
| `GET` | `/api/meta` | Supported formats + implemented vs. not implemented |
| `POST` | `/api/upload` | Multipart `file` + optional `problem_description` → file metadata + stub analysis |
| `POST` | `/api/analyze` | `{ "analysis_id": "an_..." }` → run the pipeline, return the full payload |
| `GET` | `/api/analysis/{id}` | Full analysis payload (all seven blocks) |
| `GET` | `/api/analysis/{id}/status` | Pipeline stage statuses only |
| `GET` | `/api/analysis/{id}/report/download` | Report as a Markdown attachment |
| `GET` | `/api/analyses?limit=5` | Recent analyses for the dashboard |
| `DELETE` | `/api/analysis/{id}` | Remove a stored analysis |

Interactive documentation: <http://127.0.0.1:8000/docs>

**Example**

```bash
# 1. Upload
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@samples/customer_churn_sample.csv" \
  -F "problem_description=Predict customer churn using historical customer data."

# 2. Run the pipeline
curl -X POST http://127.0.0.1:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"analysis_id":"an_77d9226d4ad5"}'
```

---

## What is real vs. modelled

| Thing | Status |
|---|---|
| File upload, type/size validation, path-traversal guard | **Real** |
| CSV / XLSX / JSON parsing | **Real** (pandas + openpyxl) |
| Row / column counts, feature types, missing values, duplicates, cardinality, class distribution, target column | **Real** |
| Task-type characterisation (classification / regression / clustering / optimisation / unknown) | **Real** (structural + keyword disambiguation) |
| Classical model training and metrics | **Real** (scikit-learn, measured on a hold-out split) |
| Quantum suitability score | **Real scoring** (6 transparent weighted factors + hard caps) |
| Comparison matrix, winner, radar data | **Real** (derived from measured inputs) |
| Recommendation, confidence, reasoning, next steps | **Real** (ordered decision gates) |
| Pipeline orchestration and persistence | **Real** |
| Markdown report download | **Real** |
| Quantum circuit execution / hardware results | **Not implemented, and not claimed** |

Mock values are gone: `models/mock/` now contains only the static pipeline-stage
definitions the UI stepper needs. Every block reports `is_mock: false`, and
`data_source` is `"real"`.

---

## Current limitations

Read these before trusting a number. The full list is in
[`backend/services/README.md`](backend/services/README.md#limitations); the most
important ones:

- **No quantum hardware is used, and no quantum advantage is claimed.** The
  quantum stage builds and executes a real QAOA circuit, but on a *local Qiskit
  Aer simulator*. Its circuit metrics and objective values are genuinely
  measured; they say nothing about performance on a real QPU.
- **The QAOA partition is not a feature selection.** It partitions a
  feature-correlation graph as an optimisation signal. It is not a validated
  selected-feature subset and does not replace classical model validation.
- **The suitability score is a prioritisation heuristic, not a physical model.**
  Its weights are defensible and fully disclosed in `quantum_analysis.suitability`,
  but they are a judgement call.
- **The classical baselines are baselines, not best results.** Models are cheap
  and untuned on purpose. A tuned ensemble will beat them.
- **Large files are sampled** above `ANALYSIS_MAX_ROWS`, and the payload says so
  in `dataset.warnings`.
- **In-memory storage.** Analyses are lost on restart and are not shared between
  workers. `utils/store.py` is the seam for a real database.
- **No authentication, no rate limiting, no upload retention policy.** Needed
  before any public deployment.
- **Report is Markdown only.** No PDF/HTML export.
- **Upload guard is client + server side but shallow** — no content sniffing, so
  a mislabelled file is parsed as whatever it actually is.

---

## Testing

```bash
cd backend
pytest              # 54 tests
```

| File | Covers |
|---|---|
| `tests/test_scenarios.py` | The three required datasets — outcome **and** reasoning |
| `tests/test_errors.py` | Every error path (bad type, empty, unparseable, too few rows, single class, long description, ...) |
| `tests/test_api_contract.py` | Every key the React pages read still exists and is usable |
| `tests/test_scoring.py` | The scoring formula, reproducibility, monotonicity, caps and bounds |

The three required scenarios:

1. **Small classification** → a model is trained, beats the majority-class
   floor, classical is reported `High` feasibility, and classical is recommended.
2. **High-dimensional feature selection** → *Quantum Feature Selection* becomes
   the top candidate, while the accuracy row still refuses to claim a quantum
   number.
3. **Optimisation framing** → the task type comes from the statement (there is no
   target column at all), *QAOA* is the top candidate, and no predictive model is
   invented.

---

## Future work

**Next — feature selection.** Insert a stage between profiling and classical
(filter / wrapper / embedded) so the chosen subset is reported and fed to both
engines. This is the single change that would most improve real quantum
feasibility, because a smaller `d` is what actually shrinks the qubit register.

**Then — a real quantum experiment.** Build the circuit, run it on a simulator,
and report the measurement. See
[plugging in real quantum algorithms](backend/services/README.md#plugging-in-real-quantum-algorithms).
The key rule: a *measured* quantum result that beats the classical control is
the only thing that should ever move a verdict toward Quantum AI.

**Platform.** Persistent `AnalysisRepository` (Postgres/Mongo), authentication,
rate limiting, per-upload retention limits, and PDF/HTML report export.
- LLM-assisted natural-language reasoning and next steps, grounded in the
  measured results.

**Phase 5 — Product**
- Report exports (PDF, HTML), saved/archived analyses, team accounts.
- Dataset registry and run-to-run comparison.

**Throughout**
- Backend tests for every service seam; frontend tests for the flow.
- Flip `data_source` from `"mock"` to `"real"` and remove the mock badges as
  each stage goes live — one stage at a time, no big-bang cutover.

---

## Contributing

1. Fork and branch off `main`.
2. Keep the decoupling rule: stages do not import each other; new behaviour goes
   behind a service module, not into a route or a React component.
3. **Never hard-code an analysis value.** Either compute it in the service that
   owns it, or read it from the API payload.
4. **Never fabricate a measurement.** If a number was not measured, label it as
   a derived value or an assumption — `comparison.criteria[*][*].basis` exists for
   exactly this. Quantum performance in particular must never be invented.
5. Run `pytest` in `backend/`, and `npm run lint` + `npm run build` in
   `frontend/`, before opening a PR.

## License

To be decided by the team.

> scores and the verdict changes with them.
