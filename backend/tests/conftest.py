"""Shared fixtures.

The three datasets named in the specification are generated here deterministically
(seeded numpy) rather than committed as binaries, so the suite stays fast, is
reproducible, and makes the *shape* of each scenario explicit in readable code.
"""

from __future__ import annotations

import io
import pathlib

import numpy as np
import pandas as pd
import pytest

# The backend package root must be importable when pytest runs from `backend/`.
BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# The three specified scenarios
# ---------------------------------------------------------------------------


def make_small_classification(n: int = 240, seed: int = 7) -> pd.DataFrame:
    """Dataset 1: a small, clean, linearly separable binary classification set."""
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(
        {
            "tenure_months": rng.integers(1, 72, n),
            "monthly_charge": rng.normal(60, 18, n).round(2),
            "avg_session_minutes": rng.normal(25, 8, n).round(2),
            "support_tickets": rng.integers(0, 6, n),
            "age": rng.integers(18, 75, n),
        }
    )
    risk = frame["monthly_charge"] / 60 + frame["support_tickets"] * 0.4
    frame["is_churned"] = np.where(risk > 1.6, "Yes", "No")
    return frame


def make_high_dimensional(n: int = 600, d: int = 48, seed: int = 11) -> pd.DataFrame:
    """Dataset 2: many mostly-noisy features, where *which* to keep is the problem.

    Only every 6th column carries signal, so the feature-selection search space
    is genuinely 2**d and a classical model still does well once the signal
    columns are found.
    """
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(
        {f"feature_{i:02d}": rng.normal(size=n) for i in range(d)}
    )
    signal = frame[[f"feature_{i:02d}" for i in range(0, d, 6)]].sum(axis=1)
    frame["target"] = np.where(signal + rng.normal(0, 0.4, n) > 0, "up", "down")
    return frame


def make_optimization(n: int = 400, seed: int = 13) -> pd.DataFrame:
    """Dataset 3: a job-scheduling/cost table, with no predictive target.

    There is no label column at all, so the task type can only come from the
    problem statement.
    """
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "job_id": [f"J{i:04d}" for i in range(n)],
            "duration": rng.integers(1, 12, n),
            "machine": rng.integers(1, 6, n),
            "priority": rng.integers(1, 4, n),
            "cost": rng.random(n).round(4),
        }
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def small_classification_csv() -> bytes:
    return make_small_classification().to_csv(index=False).encode()


@pytest.fixture
def high_dimensional_csv() -> bytes:
    return make_high_dimensional().to_csv(index=False).encode()


@pytest.fixture
def optimization_csv() -> bytes:
    return make_optimization().to_csv(index=False).encode()


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """Redirect the upload directory and frame cache into a temp folder."""
    from config import settings
    from utils import dataset_cache

    target = tmp_path / "uploads"
    target.mkdir(exist_ok=True)
    monkeypatch.setattr(settings, "upload_dir", str(target))
    dataset_cache.get_cache().clear()
    yield target
    dataset_cache.get_cache().clear()


@pytest.fixture
def client():
    """A TestClient with a clean in-memory store for every test."""
    from fastapi.testclient import TestClient

    from main import app
    from utils.store import get_repository

    get_repository()._items.clear()  # noqa: SLF001 - test isolation
    with TestClient(app) as test_client:
        yield test_client
    get_repository()._items.clear()  # noqa: SLF001


@pytest.fixture
def analyze_csv(client, upload_dir):
    """Upload a CSV, run the pipeline, and return the full analysis payload."""

    def _run(content: bytes, filename: str = "data.csv", description: str = "") -> dict:
        response = client.post(
            "/api/upload",
            files={"file": (filename, content, "text/csv")},
            data={"problem_description": description} if description else {},
        )
        assert response.status_code == 201, response.text
        analysis_id = response.json()["analysis_id"]
        result = client.post("/api/analyze", json={"analysis_id": analysis_id})
        assert result.status_code == 200, result.text
        return result.json()

    return _run
