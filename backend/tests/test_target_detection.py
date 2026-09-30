"""Target-column detection.

Target detection used to be a fixed list of six exact names plus fifteen
prefixes, so a perfectly valid dataset whose label is called `Survived`,
`species` or `diagnosis` was reported as having no target and the whole
supervised half of the pipeline was skipped.

Detection now combines three independent kinds of evidence - the column name,
the problem statement, and (as a small nudge only) the column's shape. These
tests pin the behaviour, including the cases where it must *not* invent a
target.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from utils.profiling import (
    TARGET_ACCEPT_THRESHOLD,
    normalise_name,
    resolve_target,
    score_target_candidates,
)


def _titanic(n: int = 300, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    pclass = rng.choice([1, 2, 3], n, p=[0.25, 0.25, 0.5])
    sex = rng.choice(["male", "female"], n, p=[0.65, 0.35])
    survived = ((1.6 * (sex == "female")) - 0.55 * pclass + rng.normal(0, 0.7, n) > 0).astype(int)
    return pd.DataFrame({
        "PassengerId": np.arange(1, n + 1),
        "Survived": survived,
        "Pclass": pclass,
        "Name": [f"Passenger {i}" for i in range(n)],
        "Sex": sex,
        "Age": np.round(rng.gamma(6.0, 5.0, n) + 1, 1),
        "SibSp": rng.integers(0, 4, n),
        "Parch": rng.integers(0, 4, n),
        "Ticket": [f"PC {17000 + i}" for i in range(n)],
        "Fare": np.round(rng.lognormal(0.4, 0.9, n), 4),
        "Cabin": np.where(rng.random(n) < 0.25, [f"C{i}" for i in range(n)], ""),
        "Embarked": rng.choice(["S", "C", "Q"], n, p=[0.7, 0.2, 0.1]),
    })


# ---------------------------------------------------------------------------
# The reported case
# ---------------------------------------------------------------------------


def test_titanic_survived_is_detected():
    frame = _titanic()
    target, source, candidates = resolve_target(
        frame, None, "Predict whether a passenger survived the sinking."
    )
    assert target == "Survived"
    assert source.startswith("inferred")
    assert candidates[0]["column"] == "Survived"
    assert candidates[0]["score"] >= TARGET_ACCEPT_THRESHOLD


def test_titanic_identifier_columns_are_never_the_target():
    """PassengerId / Name / Ticket are unique per row and must be rejected."""
    frame = _titanic()
    scored = {c["column"]: c for c in score_target_candidates(frame, "Predict survival.")}
    for identifier in ("PassengerId", "Name", "Ticket"):
        if identifier in scored:
            assert scored[identifier]["score"] < TARGET_ACCEPT_THRESHOLD, identifier
    target, _, _ = resolve_target(frame, None, "Predict whether a passenger survived.")
    assert target not in ("PassengerId", "Name", "Ticket", "Pclass", "Embarked", "Sex")


def test_generic_measure_words_are_not_labels():
    """`score_a` is a feature; a bare "score" must not become a target."""
    frame = pd.DataFrame({
        "score_a": np.linspace(0, 1, 120),
        "score_b": np.linspace(1, 2, 120),
        "risk_level": np.tile(["low", "high"], 60),
    })
    target, _, _ = resolve_target(frame, None, "Do something useful.")
    assert target is None


def test_no_target_is_invented_for_an_unsupervised_dataset():
    """A dataset with no label must stay unsupervised - nothing is promoted."""
    rng = np.random.default_rng(5)
    frame = pd.DataFrame({
        "amount": np.round(rng.normal(100, 20, 120), 2),
        "channel": ["web", "app"] * 60,
        "region": ["north", "south"] * 60,
    })
    target, source, _ = resolve_target(frame, None, "Group customers into segments.")
    assert target is None
    assert source is None


# ---------------------------------------------------------------------------
# The other three datasets the specification names
# ---------------------------------------------------------------------------


def test_iris_species_is_detected():
    rng = np.random.default_rng(3)
    frame = pd.DataFrame({f"sepal_{i}": rng.normal(5 + i, 0.8, 150).round(2) for i in range(4)})
    frame["species"] = np.repeat(["setosa", "versicolor", "virginica"], 50)
    target, _, _ = resolve_target(frame, None, "Classify the iris species.")
    assert target == "species"


def test_breast_cancer_diagnosis_is_detected():
    rng = np.random.default_rng(9)
    frame = pd.DataFrame({f"feature_{i}": rng.normal(0, 1, 300) for i in range(9)})
    frame["diagnosis"] = np.repeat(["M", "B"], 150)
    target, _, _ = resolve_target(frame, None, "Predict the diagnosis from the features.")
    assert target == "diagnosis"


def test_wine_quality_is_detected():
    rng = np.random.default_rng(4)
    frame = pd.DataFrame({f"measure_{i}": rng.normal(5, 1, 400).round(3) for i in range(11)})
    frame["quality"] = rng.integers(3, 10, 400)
    target, _, _ = resolve_target(frame, None, "Predict the quality rating of a wine.")
    assert target == "quality"


# ---------------------------------------------------------------------------
# Description evidence and precedence
# ---------------------------------------------------------------------------


def test_description_alone_can_identify_a_label_shaped_column():
    """No name match, but the statement names a label-shaped column."""
    frame = pd.DataFrame({
        "height_cm": np.round(np.random.default_rng(1).normal(170, 10, 100), 1),
        "verdict_code": ["A", "B", "C"] * 33 + ["A"],
    })
    target, source, _ = resolve_target(frame, None, "Predict the verdict for each record.")
    assert target == "verdict_code"
    assert source == "inferred from the problem statement"


def test_user_specified_target_always_wins():
    frame = _titanic()
    target, source, _ = resolve_target(frame, "Pclass", "Predict whether a passenger survived.")
    assert target == "Pclass"
    assert source == "user-specified"


def test_unknown_requested_target_falls_back_to_inference():
    frame = _titanic()
    target, source, _ = resolve_target(frame, "does_not_exist", "Predict survival.")
    assert target == "Survived"
    assert source != "user-specified"


def test_every_candidate_carries_its_evidence():
    """The UI explains the choice, so the reasons must be populated."""
    frame = _titanic()
    candidates = score_target_candidates(frame, "Predict whether a passenger survived.")
    assert candidates
    for candidate in candidates:
        assert candidate["reasons"], candidate
        assert isinstance(candidate["score"], int)


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Survived", "survived"), ("SURVIVED", "survived"), ("sale_price", "sale price"),
     ("  Target  ", "target"), ("is-churned", "is churned")],
)
def test_names_are_normalised(raw, expected):
    assert normalise_name(raw) == expected


def test_underscores_and_spaces_are_equivalent():
    a = score_target_candidates(
        pd.DataFrame({"sale_price": [1.0, 2.0, 3.0]}), "Estimate the sale price."
    )
    b = score_target_candidates(
        pd.DataFrame({"sale price": [1.0, 2.0, 3.0]}), "Estimate the sale price."
    )
    assert a[0]["score"] == b[0]["score"]
