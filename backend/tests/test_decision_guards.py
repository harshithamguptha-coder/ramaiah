"""Guards on the decision engine.

These are the failure modes that would make Q-Compass dishonest: recommending
Quantum AI for a dataset it could not even analyse, or mistaking a boolean
feature for the label. Both were real bugs, so both are pinned here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from services import dataset_service, problem_service
from utils.dataset_cache import get_frame


def _analyse(tmp_path, frame, name, description):
    """Run the real pipeline over a DataFrame written to a temp upload dir."""
    from config import settings

    settings.upload_dir = str(tmp_path)
    from utils import dataset_cache

    dataset_cache.get_cache().clear()

    path = tmp_path / name
    frame.to_csv(path, index=False)
    meta = {
        "file_id": f"fl_{name}",
        "file_name": name,
        "file_size_bytes": path.stat().st_size,
        "file_type": "csv",
        "stored_path": str(path),
    }
    # The description is evidence for target detection, exactly as the upload
    # route supplies it.
    dataset = dataset_service.build_dataset(
        meta, problem_description=description
    )
    frame_obj = get_frame(meta["file_id"])
    problem = problem_service.build_problem(description, dataset, frame_obj)
    return dataset, problem, frame_obj


# ---------------------------------------------------------------------------
# A boolean feature is not a label
# ---------------------------------------------------------------------------


def test_flag_column_is_not_mistaken_for_the_target(tmp_path):
    """`has_garage` matches a label pattern but is a feature, not the label."""
    rng = np.random.default_rng(4)
    frame = pd.DataFrame(
        {
            "area_sqft": rng.normal(1800, 500, 200).round(1),
            "rooms": rng.integers(1, 6, 200),
            "age_years": rng.integers(0, 90, 200),
            "has_garage": rng.integers(0, 2, 200),  # pattern match, but a feature
            "sale_price": rng.lognormal(12, 0.2, 200).round(2),  # the real target
        }
    )
    dataset, problem, _ = _analyse(
        tmp_path, frame, "houses.csv", "Estimate the sale price of a house."
    )
    assert dataset["target_column"] == "sale_price", (
        "the named, description-matched column must win over a 0/1 flag"
    )
    assert dataset["target_column"] != "has_garage"
    assert problem["problem_type"] == "regression"


def test_bare_flag_is_not_guessed_when_a_continuous_column_exists(tmp_path):
    """With no name or description evidence, nothing is invented."""
    frame = pd.DataFrame(
        {"flag1": np.tile([1, 0], 60), "score_a": np.linspace(0, 1, 120)}
    )
    dataset, _, _ = _analyse(tmp_path, frame, "bare.csv", "Do something useful.")
    assert dataset["target_column"] is None, (
        "a column with no name or description evidence must not become a target"
    )


def test_string_label_is_still_detected(tmp_path):
    """The fix must not break the common Yes/No label case."""
    frame = pd.DataFrame(
        {
            "tenure": np.arange(100),
            "has_garage": np.tile([0, 1], 50),
            "is_churned": ["Yes", "No"] * 50,
        }
    )
    dataset, _, _ = _analyse(tmp_path, frame, "churn.csv", "Predict churn.")
    assert dataset["target_column"] == "is_churned"
    assert dataset["problem_type"] == "classification"


def test_numeric_label_used_when_no_continuous_column_exists(tmp_path):
    """A 0/1 label is still usable when nothing else could be the target."""
    frame = pd.DataFrame(
        {
            "fraud_flag": np.tile([1, 0], 60),
            "region": ["North", "South", "East", "West"] * 30,
        }
    )
    dataset, _, _ = _analyse(tmp_path, frame, "fraud.csv", "Detect fraud.")
    assert dataset["target_column"] == "fraud_flag"
    assert dataset["problem_type"] == "classification"


def test_domain_named_label_is_detected_even_with_a_continuous_column(tmp_path):
    """`fraud_flag` carries a label word, so it is chosen over `score_a`."""
    frame = pd.DataFrame(
        {"fraud_flag": np.tile([1, 0], 60), "score_a": np.linspace(0, 1, 120)}
    )
    dataset, problem, _ = _analyse(tmp_path, frame, "fraud.csv", "Detect fraud.")
    assert dataset["target_column"] == "fraud_flag"
    assert problem["problem_type"] == "classification"

    # An explicit target still overrides any inference.
    from services import dataset_service

    path = tmp_path / "fraud.csv"
    frame.to_csv(path, index=False)
    explicit = dataset_service.build_dataset(
        {
            "file_id": "fl_explicit",
            "file_name": "fraud.csv",
            "file_size_bytes": path.stat().st_size,
            "file_type": "csv",
            "stored_path": str(path),
        },
        target_column="score_a",
    )
    assert explicit["target_column"] == "score_a"
    assert explicit["target_source"] == "user-specified"


# ---------------------------------------------------------------------------
# Quantum must never be recommended for data we could not analyse
# ---------------------------------------------------------------------------


def _recommend(tmp_path, frame, name, description):
    from services import (
        classical_service,
        comparison_service,
        quantum_service,
        recommendation_service,
    )

    dataset, problem, frame_obj = _analyse(tmp_path, frame, name, description)
    classical = classical_service.run(dataset, problem, "an_test", frame_obj)
    quantum = quantum_service.run(dataset, problem, "an_test", frame_obj)
    comparison = comparison_service.run(classical, quantum, dataset, "an_test")
    return classical, quantum, recommendation_service.run(
        comparison, classical, quantum, problem, dataset, "an_test"
    )


def test_single_class_never_recommends_quantum(tmp_path):
    """A degenerate label is a data problem, not a quantum opportunity."""
    rng = np.random.default_rng(8)
    frame = pd.DataFrame({"a": rng.normal(size=120), "b": rng.normal(size=120)})
    frame["label"] = ["only"] * 120
    classical, _, recommendation = _recommend(
        tmp_path, frame, "single.csv", "Classify the records."
    )
    assert classical["status"] == "skipped"
    assert recommendation["approach_key"] != "quantum"
    assert recommendation["gate"] in ("G5", "G4")


def test_too_few_rows_never_recommends_quantum(tmp_path):
    """Six rows cannot support any experiment, quantum or otherwise."""
    frame = pd.DataFrame(
        {"a": [1, 2, 3, 4, 5, 6], "b": [2, 4, 6, 8, 10, 12], "label": ["p", "n", "p", "n", "p", "n"]}
    )
    classical, _, recommendation = _recommend(
        tmp_path, frame, "few.csv", "Classify the records."
    )
    assert classical["status"] == "skipped"
    assert recommendation["approach_key"] != "quantum"


def test_unparseable_dataset_never_recommends_quantum(tmp_path):
    frame = pd.DataFrame({"a": [1, 2], "b": [3, 4]})  # no usable label
    classical, _, recommendation = _recommend(
        tmp_path, frame, "notarget.csv", "Do something useful with this."
    )
    assert classical["status"] == "skipped"
    assert recommendation["approach_key"] != "quantum"


def test_genuine_optimisation_still_recommends_quantum(tmp_path):
    """The guard must not have made Quantum AI unreachable.

    A real combinatorial problem clears every gate, so Quantum AI is the
    correct - and now well-evidenced - answer.
    """
    rng = np.random.default_rng(3)
    frame = pd.DataFrame(
        {
            "job_id": [f"J{i}" for i in range(300)],
            "duration": rng.integers(1, 12, 300),
            "machine": rng.integers(1, 6, 300),
            "cost": rng.random(300).round(4),
        }
    )
    classical, quantum, recommendation = _recommend(
        tmp_path,
        frame,
        "sched.csv",
        "Schedule jobs to minimise total cost under capacity constraints; this is "
        "a combinatorial optimisation and assignment problem.",
    )
    assert recommendation["approach_key"] == "quantum", (
        f"expected Quantum AI, got {recommendation['approach_key']} "
        f"via {recommendation['gate']}"
    )
    assert recommendation["gate"] == "G3"
    assert "QAOA" in quantum["potential_methods"]
    assert quantum["execution"]["hardware_executed"] is False
