"""The response contract the existing frontend depends on must not drift.

These tests are the guard rail for "replace the engine, keep the API": they
assert that every key each page reads still exists, with a usable type, after
the mock engine was replaced by the real one.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from conftest import make_small_classification

# (block, keys) exactly as the React pages read them.
REQUIRED_BLOCK_KEYS = {
    "dataset": [
        "file_id", "file_name", "file_size_bytes", "file_size_display", "file_type",
        "uploaded_at", "rows", "column_count", "column_names", "numerical_features",
        "categorical_features", "missing_values", "missing_percent", "target_column",
        "feature_names", "feature_count", "memory_footprint_mb", "profile_method",
        "profiled", "is_mock", "note",
    ],
    "problem": [
        "description", "task_type", "task_type_confidence", "learning_paradigm",
        "target_column", "keywords", "detected_modalities", "summary", "is_mock", "note",
    ],
    "classical_analysis": [
        "dataset_size", "candidates", "baseline_model", "best_model",
        "estimated_complexity", "resource_requirements", "summary", "is_mock", "note",
    ],
    "quantum_analysis": [
        "suitability_score", "suitability_label", "confidence", "candidate_algorithms",
        "primary_algorithm", "qubits_required", "qubits_estimate_range",
        "circuit_complexity", "estimated_resources", "feasibility",
        "potential_advantages", "limitations", "encoding_strategies", "is_mock", "note",
    ],
    "comparison": [
        "criteria", "weights", "weighted_scores", "winner", "winner_label",
        "radar_axes", "radar_series", "summary", "is_mock", "note",
    ],
    "recommendation": [
        "recommended_approach", "approach_key", "confidence", "confidence_label",
        "headline", "summary", "scores", "reasons", "advantages", "limitations",
        "suggested_next_steps", "roadmap", "decision_basis",
        "confidence_in_underlying_data", "is_mock", "disclaimer",
    ],
}

TOP_LEVEL_KEYS = [
    "analysis_id", "status", "data_source", "pipeline", "dataset", "problem",
    "classical_analysis", "quantum_analysis", "comparison", "recommendation",
    "report", "warnings",
]


@pytest.fixture
def payload(analyze_csv):
    return analyze_csv(
        make_small_classification().to_csv(index=False).encode(),
        description="Classify whether a customer will churn this month.",
    )


def test_top_level_contract(payload):
    for key in TOP_LEVEL_KEYS:
        assert key in payload, f"missing top-level key: {key}"
    assert payload["data_source"] == "real"
    assert payload["mock_data"] is False
    assert payload["status"] == "completed"
    json.dumps(payload)  # the whole payload must be JSON-serialisable


@pytest.mark.parametrize("block", sorted(REQUIRED_BLOCK_KEYS))
def test_block_keys_present(payload, block):
    section = payload[block]
    for key in REQUIRED_BLOCK_KEYS[block]:
        assert key in section, f"{block}.{key} is missing"


def test_pipeline_stages_are_complete(payload):
    stages = payload["pipeline"]
    assert len(stages) == 7
    assert all(stage["status"] == "completed" for stage in stages)


def test_nested_shapes_the_charts_depend_on(payload):
    for candidate in payload["classical_analysis"]["candidates"]:
        assert isinstance(candidate["accuracy"], (float, type(None)))
        assert isinstance(candidate["f1_score"], (float, type(None)))
        assert isinstance(candidate["training_time_sec"], (int, float))
        assert isinstance(candidate["complexity"], str)
        assert isinstance(candidate["notes"], str)

    for method in payload["quantum_analysis"]["candidate_algorithms"]:
        assert isinstance(method["problem_fitting"], float)
        assert isinstance(method["qubits_required"], int)
        assert method["suitability"] in ("high", "medium", "exploratory")

    resources = payload["quantum_analysis"]["estimated_resources"]
    # The UI calls .toLocaleString() on this, so it must be a number.
    assert isinstance(resources["shots"], int)
    for key in ("provider", "expected_queue_time", "cost_per_shot", "notes"):
        assert isinstance(resources[key], str)

    comparison = payload["comparison"]
    assert len(comparison["radar_axes"]) == len(comparison["criteria"])
    for series in comparison["radar_series"]:
        assert len(series["values"]) == len(comparison["radar_axes"])
    for row in comparison["criteria"]:
        for key in ("classical", "quantum", "hybrid"):
            assert isinstance(row[key]["score"], int)
            assert isinstance(row[key]["value"], str)
            assert isinstance(row[key]["note"], str)

    for reason in payload["recommendation"]["reasons"]:
        assert set(reason) >= {"title", "detail", "impact"}
    for phase in payload["recommendation"]["roadmap"]:
        assert set(phase) >= {"phase", "title", "status"}


def test_report_contract(payload):
    report = payload["report"]
    assert report["is_mock"] is False
    assert [s["key"] for s in report["sections"]] == [
        "problem_overview", "dataset_summary", "classical_analysis", "quantum_analysis",
        "comparison", "recommended_approach", "reasoning", "limitations", "next_steps",
    ]
    assert report["markdown"].startswith("# Q-Compass Analysis Report")


def test_summary_listing_shape(client, upload_dir, analyze_csv):
    analyze_csv(
        make_small_classification().to_csv(index=False).encode(),
        description="Classify whether a customer will churn this month.",
    )
    listing = client.get("/api/analyses?limit=5").json()
    assert listing["count"] == 1
    item = listing["items"][0]
    for key in (
        "analysis_id", "created_at", "file_name", "problem_description",
        "task_type", "recommended_approach", "confidence", "status",
    ):
        assert key in item


def test_status_and_delete_endpoints(client, upload_dir, analyze_csv):
    analyze_csv(make_small_classification().to_csv(index=False).encode())
    listing = client.get("/api/analyses").json()
    analysis_id = listing["items"][0]["analysis_id"]

    status = client.get(f"/api/analysis/{analysis_id}/status").json()
    assert status["data_source"] == "real"
    assert len(status["pipeline"]) == 7

    download = client.get(f"/api/analysis/{analysis_id}/report/download")
    assert download.status_code == 200
    assert "text/markdown" in download.headers["content-type"]

    assert client.delete(f"/api/analysis/{analysis_id}").status_code == 200
    assert client.delete(f"/api/analysis/{analysis_id}").status_code == 404


def test_health_and_meta_report_real_mode(client):
    assert client.get("/api/health").json()["mode"] == "real"
    meta = client.get("/api/meta").json()
    assert meta["mock_data"] is False
    assert meta["quantum"]["hardware_executed"] is False
    assert "classical-model-training" in meta["implemented"]


# ---------------------------------------------------------------------------
# Invariant the frontend depends on
# ---------------------------------------------------------------------------


def test_analyze_always_returns_all_seven_blocks(client, upload_dir, small_classification_csv):
    """`POST /api/analyze` must return every block, even when a stage is skipped.

    The React pages each read one top-level block. If the pipeline ever returned
    early, the corresponding route would have nothing to render, so this
    invariant is what keeps all seven stages visible.
    """
    response = client.post(
        "/api/upload", files={"file": ("d.csv", small_classification_csv, "text/csv")}
    )
    analysis_id = response.json()["analysis_id"]
    payload = client.post("/api/analyze", json={"analysis_id": analysis_id}).json()

    for block in REQUIRED_BLOCK_KEYS:
        assert block in payload, f"{block} missing from /api/analyze"
        assert isinstance(payload[block], dict), f"{block} must be an object"

    # The stored record (what a page refresh re-fetches) must match.
    stored = client.get(f"/api/analysis/{analysis_id}").json()
    for block in REQUIRED_BLOCK_KEYS:
        assert block in stored, f"{block} missing from GET /api/analysis"


def test_analyze_returns_all_blocks_when_classical_is_skipped(client, upload_dir):
    """A skipped classical stage must not remove the blocks after it.

    This is the case that used to make the downstream pages disappear: without a
    target column the classical stage is skipped, and the rest of the pipeline
    must still complete.
    """
    frame = pd.DataFrame({"a": np.arange(40), "b": np.arange(40) * 1.5, "c": np.arange(40) % 7})
    response = client.post(
        "/api/upload", files={"file": ("notarget.csv", frame.to_csv(index=False).encode(), "text/csv")}
    )
    analysis_id = response.json()["analysis_id"]
    payload = client.post("/api/analyze", json={"analysis_id": analysis_id}).json()

    assert payload["classical_analysis"]["status"] == "skipped"
    assert payload["dataset"]["target_column"] is None
    # Everything downstream still exists and is renderable.
    assert payload["quantum_analysis"]["suitability_score"] >= 0
    assert payload["comparison"]["weighted_scores"]
    assert payload["recommendation"]["recommended_approach"]
    assert payload["report"]["sections"]


def test_target_column_reaches_the_pipeline(client, upload_dir):
    """The upload target_column field is honoured end to end."""
    import numpy as np
    import pandas as pd

    frame = pd.DataFrame(
        {
            "area_sqft": np.linspace(800, 3000, 120),
            "rooms": np.tile([2, 3, 4, 5], 30),
            "sale_price": np.linspace(150_000, 420_000, 120),
        }
    )
    response = client.post(
        "/api/upload",
        files={"file": ("houses.csv", frame.to_csv(index=False).encode(), "text/csv")},
        data={"target_column": "sale_price", "problem_description": "Estimate the sale price."},
    )
    analysis_id = response.json()["analysis_id"]
    payload = client.post("/api/analyze", json={"analysis_id": analysis_id}).json()

    assert payload["dataset"]["target_column"] == "sale_price"
    assert payload["dataset"]["target_source"] == "user-specified"
    # A continuous target is a regression task, so it is actually trained.
    assert payload["problem"]["problem_type"] == "regression"
    assert payload["classical_analysis"]["task"] == "regression"
    assert payload["classical_analysis"]["best_model"]["primary_metric"] == "r2"
    assert payload["classical_analysis"]["best_model"]["r2"] is not None
