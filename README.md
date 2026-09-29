# Q-Compass — Quantum Readiness & AI Decision Engine

> **Prototype status.** This repository is the **base application**: a complete,
> working end-to-end flow (Dashboard → Upload → Analysis → Comparison →
> Recommendation → Report) built on **mock analysis data**. Only dataset
> ingestion and structural profiling are real. The architecture is designed so
> the real classical-ML, quantum, comparison and recommendation engines can be
> implemented independently and plugged in later without changing the UI or the
> API contract.

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
- [What is real vs. mocked](#what-is-real-vs-mocked)
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

Every page and every transition works today. The pages after *Problem Analysis*
display deterministic placeholder values, all clearly marked with a
`Mock data` badge so nobody mistakes a fabricated number for a measurement.

### Pipeline stages

| # | Stage | Route | Status |
|---|-------|-------|--------|
| 1 | Dataset uploaded | `/upload` | **Real** (ingest + structural profile) |
| 2 | Dataset profiling | `/analysis` | **Real** (shape) / mock (task inference) |
| 3 | Classical analysis | `/classical` | Mock |
| 4 | Quantum analysis | `/quantum` | Mock |
| 5 | Comparison | `/comparison` | Mock |
| 6 | Recommendation | `/recommendation` | Mock |
| 7 | Report generation | `/report` | **Real** (Markdown export) |

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
                                          models/mock/*  (swap point)
                                                    │
                                            utils/store.py  (DB seam)
```

### Where to plug in the real engines

| Concern | File to replace | What you add |
|---|---|---|
| Dataset parsing / profiling | `utils/profiling.py` | pandas / Polars reader |
| Problem classification | `models/mock/dataset.py` | A real classifier or LLM classifier |
| Classical benchmarking | `services/classical_service.py` | scikit-learn / XGBoost training + CV |
| Feature selection | *(new stage between profiling and classical)* | Filter / wrapper / embedded selection |
| Quantum suitability | `services/quantum_service.py` | Penalty-based scoring model |
| Quantum experiment | `services/quantum_service.py` | Qiskit / PennyLane circuit + simulator |
| Comparison scoring | `services/comparison_service.py` | Real weighting / learned ranker |
| Recommendation | `services/recommendation_service.py` | Rules engine or LLM-assisted explanation |
| Persistence | `utils/store.py` | Implement `AnalysisRepository` with SQL/Postgres/Mongo |

The payload contract is fixed, so the frontend needs **no changes** when a real
engine lands:

```jsonc
{
  "analysis_id": "an_77d9226d4ad5",
  "status": "completed",
  "data_source": "mock",          // flip to "real" when engines are live
  "dataset":             { },     // stage 2
  "problem":             { },     // stage 2
  "classical_analysis":  { },     // stage 3
  "quantum_analysis":    { },     // stage 4
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
│   ├── services/
│   │   ├── analysis_service.py       # orchestrator (owns stage order)
│   │   ├── dataset_service.py        # ingest + profile
│   │   ├── classical_service.py      # stage 3  <-- replace me
│   │   ├── quantum_service.py        # stage 4  <-- replace me
│   │   ├── comparison_service.py     # stage 5  <-- replace me
│   │   ├── recommendation_service.py # stage 6  <-- replace me
│   │   └── report_service.py         # stage 7
│   ├── models/
│   │   ├── schemas.py                # Pydantic request/response contracts
│   │   └── mock/                     # ALL mock data lives here
│   │       ├── common.py  dataset.py  classical.py  quantum.py
│   │       ├── comparison.py  recommendation.py  report.py  pipeline.py
│   └── utils/
│       ├── store.py                  # database seam (AnalysisRepository)
│       ├── profiling.py              # structural CSV/JSON profiler
│       ├── file_utils.py             # upload validation, path-traversal guard
│       ├── ids.py  formatting.py  logging_config.py
│   ├── uploads/                      # .gitkeep only
│   └── tests/
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
4. **Classical / Quantum / Comparison / Recommendation / Report** — populated
   with labelled placeholder data.

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

## What is real vs. mocked

| Thing | Status |
|---|---|
| File upload, type/size validation, path-traversal guard | **Real** |
| Row / column counts, numerical vs categorical split, missing values, target-column heuristic | **Real** (CSV + JSON) |
| Pipeline orchestration and persistence | **Real** |
| Markdown report download | **Real** |
| Task-type inference | Keyword heuristic (placeholder) |
| Classical accuracies, training times, complexity | **Mock** |
| Quantum suitability, qubit counts, circuit depth, feasibility | **Mock** |
| Comparison scores, winner, radar data | **Mock** |
| Recommendation, confidence, reasoning, next steps | **Mock** |
| XLSX cell-level parsing | Not implemented (no spreadsheet dependency) |

Mock values are **deterministic**: they are seeded from the analysis id, so the
same upload always produces the same report and demos are reproducible.

Every mock block carries `is_mock: true` and a `note`, and the UI renders a
`Mock data` badge. The recommendation carries an explicit disclaimer.

> **Note on the verdict.** With the current placeholder scores the pipeline
> usually concludes **Classical AI** (92 vs 79 hybrid vs 36 quantum). That is
> the mock weighting doing its job, not a hard-coded answer — swap in real

---

## Current limitations

- **No real intelligence.** Classical, quantum, comparison and recommendation are
  placeholders. Numbers are illustrative, not measurements.
- **In-memory storage.** Analyses live in process memory — they are lost on
  restart and are not shared between workers. `utils/store.py` is the seam for a
  real database.
- **XLSX is accepted but not parsed.** Uploading works; cell-level profiling is
  skipped to avoid a spreadsheet dependency. Add `openpyxl` to enable it.
- **Full-file scanning.** The profiler samples the first 500 rows of a CSV for
  type inference, but counts every row for the row total. Very large files are
  not streamed.
- **No authentication, no rate limiting, no upload retention policy.** Fine for
  a prototype on a trusted network; all three are needed before any public
  deployment.
- **No tests yet.** `backend/tests/` is scaffolded but empty.
- **Report is Markdown only.** No PDF/HTML export.
- **Upload guard is client + server side but shallow** — content sniffing is not
  performed, so a mislabelled file will be accepted and profile as whatever it
  parses as.

---

## Future implementation plan

**Phase 1 — Real data foundation**
- Pandas/Polars-backed loader; parse XLSX via `openpyxl`.
- Full profiling: distributions, correlations, class balance, cardinality.
- Persistent `AnalysisRepository` (Postgres via SQLAlchemy, or Mongo).
- Authentication, rate limiting, per-upload size/retention limits.

**Phase 2 — Classical ML**
- Problem classifier (rule-based + LLM-assisted) replacing the keyword heuristic.
- **Feature selection stage** inserted between profiling and classical: filter,
  wrapper and embedded methods, with the chosen subset reported.
- scikit-learn / XGBoost benchmarks with cross-validation, precision/recall/F1,
  confusion matrices and learning curves.
- Measured baselines replace every mocked accuracy and timing.

**Phase 3 — Quantum analysis**
- Penalty-based quantum suitability model (feature count, depth, noise, data
  size, problem type).
- Qiskit / PennyLane circuit construction on the reduced feature set.
- Simulator execution first; hardware only behind an explicit flag.
- Shot counts, noise models, and honest error bars.

**Phase 4 — Comparison & recommendation**
- Configurable, transparent weighting across the eight criteria.
- Learned ranker or rules engine for the final verdict.
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
3. Never hard-code an analysis value in the UI — add it to `models/mock/` or
   read it from the API payload.
4. Run `npm run lint` and `npm run build` in `frontend/` before opening a PR.

## License

To be decided by the team.

> scores and the verdict changes with them.
