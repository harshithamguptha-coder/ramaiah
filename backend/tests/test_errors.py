"""Error handling: the app must explain problems, not crash on them."""

from __future__ import annotations

import io
import json

import numpy as np
import pandas as pd
import pytest

from utils.errors import (
    InsufficientSamplesError,
    InvalidProblemDescriptionError,
    ParseError,
    UnsupportedFileTypeError,
)
from utils.profiling import load_dataframe


# ---------------------------------------------------------------------------
# Upload-time validation
# ---------------------------------------------------------------------------


def test_unsupported_file_type_is_rejected(client, upload_dir):
    response = client.post(
        "/api/upload", files={"file": ("data.txt", b"a,b\n1,2", "text/plain")}
    )
    assert response.status_code == 415
    assert "Unsupported file type" in response.json()["detail"]


def test_empty_file_is_rejected(client, upload_dir):
    response = client.post("/api/upload", files={"file": ("data.csv", b"", "text/csv")})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_oversized_file_is_rejected(client, upload_dir, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    response = client.post(
        "/api/upload", files={"file": ("data.csv", b"a,b\n1,2\n3,4", "text/csv")}
    )
    assert response.status_code == 413
    assert "limit" in response.json()["detail"].lower()


def test_missing_analysis_id_is_404(client):
    assert client.get("/api/analysis/an_missing").status_code == 404


def test_analyze_without_id_or_file_is_400(client):
    assert client.post("/api/analyze", json={}).status_code == 400


# ---------------------------------------------------------------------------
# Parser-level errors are typed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "extension"),
    [(b"", ".csv"), (b"{not valid json", ".json"), (b"\n\n\n", ".csv")],
)
def test_malformed_content_raises_typed_errors(payload, extension):
    with pytest.raises((ParseError, UnsupportedFileTypeError)) as excinfo:
        load_dataframe(payload, extension)
    # The message is safe to show a user.
    assert isinstance(excinfo.value.message, str)
    assert excinfo.value.message


def test_unknown_extension_raises_unsupported():
    with pytest.raises(UnsupportedFileTypeError) as excinfo:
        load_dataframe(b"a,b", ".parquet")
    assert excinfo.value.status_code == 415


# ---------------------------------------------------------------------------
# Degradation: a bad dataset still returns a complete, explainable payload
# ---------------------------------------------------------------------------


def test_unparseable_file_produces_an_explained_payload(client, upload_dir):
    """The pipeline must not 500 on a file it cannot parse."""
    response = client.post(
        "/api/upload", files={"file": ("broken.json", b"{oops", "application/json")}
    )
    assert response.status_code == 201
    analysis_id = response.json()["analysis_id"]

    result = client.post("/api/analyze", json={"analysis_id": analysis_id})
    assert result.status_code == 200
    payload = result.json()

    dataset = payload["dataset"]
    assert dataset["parse_error"]["error_code"] in ("parse_error", "json_decode_error")
    assert dataset["rows"] == 0
    # Every block is still present and JSON-serialisable.
    for key in (
        "problem", "classical_analysis", "quantum_analysis",
        "comparison", "recommendation", "report",
    ):
        assert key in payload
    assert payload["classical_analysis"]["status"] == "skipped"
    assert payload["recommendation"]["approach_key"] in ("classical", "hybrid", "quantum")
    json.dumps(payload)  # must be serialisable


def test_header_only_csv_is_handled(client, upload_dir):
    """A header with no data rows is reported as an empty dataset, not a crash."""
    header_only = b"a,b,c\n"
    response = client.post("/api/upload", files={"file": ("h.csv", header_only, "text/csv")})
    analysis_id = response.json()["analysis_id"]
    payload = client.post("/api/analyze", json={"analysis_id": analysis_id}).json()
    assert payload["dataset"]["rows"] == 0
    assert payload["dataset"]["parse_error"]["error_code"] == "empty_dataset"
    assert "no data rows" in payload["dataset"]["parse_error"]["detail"]
    assert payload["classical_analysis"]["status"] == "skipped"
    assert any("empty_dataset" in w for w in payload["warnings"])


def test_single_class_target_is_skipped(client, upload_dir):
    """A one-class label cannot be classified; say so instead of dividing by zero."""
    frame = pd.DataFrame({"a": np.arange(60), "b": np.arange(60) * 2, "label": ["x"] * 60})
    response = client.post(
        "/api/upload", files={"file": ("one.csv", frame.to_csv(index=False).encode(), "text/csv")}
    )
    analysis_id = response.json()["analysis_id"]
    payload = client.post("/api/analyze", json={"analysis_id": analysis_id}).json()
    assert payload["classical_analysis"]["status"] == "skipped"
    assert "single class" in payload["classical_analysis"]["summary"]


def test_too_few_rows_is_skipped(client, upload_dir):
    frame = pd.DataFrame({"a": [1, 2, 3], "label": ["p", "n", "p"]})
    response = client.post(
        "/api/upload", files={"file": ("few.csv", frame.to_csv(index=False).encode(), "text/csv")}
    )
    analysis_id = response.json()["analysis_id"]
    payload = client.post("/api/analyze", json={"analysis_id": analysis_id}).json()
    assert payload["classical_analysis"]["status"] == "skipped"


def test_non_numeric_data_is_handled_for_numeric_requirement(client, upload_dir):
    """All-categorical input must not crash the imputer/scaler."""
    frame = pd.DataFrame(
        {
            "colour": ["red", "blue", "green", "red", "blue", "green"] * 10,
            "size": ["s", "m", "l", "s", "m", "l"] * 10,
            "label": ["yes", "no", "yes", "no", "yes", "no"] * 10,
        }
    )
    response = client.post(
        "/api/upload", files={"file": ("cat.csv", frame.to_csv(index=False).encode(), "text/csv")}
    )
    analysis_id = response.json()["analysis_id"]
    payload = client.post("/api/analyze", json={"analysis_id": analysis_id}).json()
    assert payload["classical_analysis"]["status"] in ("completed", "skipped")
    assert payload["dataset"]["numerical_features"] == 0
    # colour, size and the label column are all categorical.
    assert payload["dataset"]["categorical_features"] == 3
    assert payload["classical_analysis"]["task"] == "classification"


def test_invalid_problem_description_length(client, upload_dir):
    frame = pd.DataFrame({"a": range(30), "label": ["p", "n"] * 15})
    response = client.post(
        "/api/upload",
        files={"file": ("d.csv", frame.to_csv(index=False).encode(), "text/csv")},
        data={"problem_description": "x" * 5000},
    )
    # Rejected at the boundary rather than silently truncated.
    assert response.status_code == 422
    assert "detail" in response.json()

    # The same limit applies when it arrives on the analyze body.
    ok = client.post(
        "/api/upload", files={"file": ("d.csv", frame.to_csv(index=False).encode(), "text/csv")}
    )
    second = client.post(
        "/api/analyze",
        json={"analysis_id": ok.json()["analysis_id"], "problem_description": "y" * 5000},
    )
    assert second.status_code == 422


def test_unknown_target_column_is_ignored_with_a_warning(client, upload_dir):
    frame = pd.DataFrame({"a": range(40), "label": ["p", "n"] * 20})
    response = client.post(
        "/api/upload",
        files={"file": ("t.csv", frame.to_csv(index=False).encode(), "text/csv")},
        data={"target_column": "does_not_exist"},
    )
    analysis_id = response.json()["analysis_id"]
    payload = client.post("/api/analyze", json={"analysis_id": analysis_id}).json()
    # It falls back to auto-detection instead of failing.
    assert payload["dataset"]["target_column"] == "label"
    assert payload["dataset"]["target_source"] != "user-specified", (
        "an unknown requested target must not be reported as user-specified"
    )
    assert payload["dataset"]["target_source"].startswith("inferred"), (
        "falling back to detection must be reported as an inference"
    )
