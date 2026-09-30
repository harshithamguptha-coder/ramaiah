"""Data-quality findings must never stop the pipeline.

Regression tests for a report where the UI showed "This stage did not produce
any data" on a perfectly good 150-row dataset that happened to contain one
duplicate row. The duplicates were only ever a *warning*; the real cause was
that the file has no header row, so pandas consumed the first data row as the
header. Both facts are pinned here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from utils.profiling import _header_looks_like_data, load_dataframe, profile_dataframe

IRIS_HEADERLESS = (
    "5.1,3.5,1.4,0.2,Iris-setosa\n"
    "4.9,3.0,1.4,0.2,Iris-setosa\n"
    "4.7,3.2,1.3,0.2,Iris-setosa\n"
    "4.6,3.1,1.5,0.2,Iris-setosa\n"
    "5.8,2.7,5.1,1.9,Iris-virginica\n"
    "5.8,2.7,5.1,1.9,Iris-virginica\n"   # the duplicate
    "6.3,3.3,6.0,2.5,Iris-virginica\n"
).encode()


# ---------------------------------------------------------------------------
# Duplicates are data-quality information, never fatal
# ---------------------------------------------------------------------------


def test_duplicate_rows_are_reported_but_not_fatal():
    profile = profile_dataframe(load_dataframe(IRIS_HEADERLESS, ".csv"))
    assert profile["duplicate_rows"] == 1
    assert profile["duplicate_percent"] == pytest.approx(14.29, abs=0.1)
    # The count stays visible...
    assert any("duplicate" in w.lower() for w in profile["warnings"])
    # ...and the dataset is still fully profiled.
    assert profile["rows"] > 0
    assert profile["columns"] == 5
    assert profile["feature_count"] == 4
    assert "parse_error" not in profile


def test_duplicate_warning_says_the_analysis_continues():
    profile = profile_dataframe(load_dataframe(IRIS_HEADERLESS, ".csv"))
    message = " ".join(profile["warnings"]).lower()
    assert "continues" in message, "the warning must state the analysis is not blocked"


def test_duplicate_warning_is_grammatically_correct():
    """One duplicate is '1 duplicate row', not '1 duplicated rows'."""
    single = profile_dataframe(load_dataframe(IRIS_HEADERLESS, ".csv"))
    assert any("1 duplicate row detected" in w for w in single["warnings"])

    # Three identical rows means two duplicates (the first is the original).
    two = pd.DataFrame({"a": [1, 1, 1], "b": [2, 2, 2], "label": ["x", "x", "x"]})
    assert any("2 duplicate rows detected" in w for w in profile_dataframe(two)["warnings"])


def test_many_duplicates_still_do_not_block_profiling():
    heavy = pd.DataFrame({"a": [1] * 90 + list(range(10)), "label": ["x"] * 90 + ["y"] * 10})
    profile = profile_dataframe(heavy)
    assert profile["duplicate_rows"] == 89
    assert profile["rows"] == 100
    assert profile["feature_count"] == 1
    assert profile["target_column"] == "label"


# ---------------------------------------------------------------------------
# The real cause: headerless files
# ---------------------------------------------------------------------------


def test_headerless_csv_restores_the_lost_row_and_finds_a_target():
    frame = load_dataframe(IRIS_HEADERLESS, ".csv")
    # 7 data lines, not 6: the first line is data, not a header.
    assert len(frame) == 7
    assert list(frame.columns) == ["feature_1", "feature_2", "feature_3", "feature_4", "target"]

    profile = profile_dataframe(frame)
    assert profile["target_column"] == "target"
    # The fixture contains two species (setosa, virginica).
    assert profile["class_count"] == 2
    assert profile["problem_type"] == "classification"


def test_header_detection_distinguishes_headers_from_data():
    with_header = pd.DataFrame({"sepal_length": [5.1, 4.9], "species": ["a", "b"]})
    assert not _header_looks_like_data(with_header)

    without_header = load_dataframe(IRIS_HEADERLESS, ".csv")
    assert not _header_looks_like_data(without_header)  # already repaired


def test_headered_csv_is_untouched():
    """The overwhelmingly common case must not be rewritten."""
    blob = b"a,b,c\n1,2,3\n4,5,6\n"
    frame = load_dataframe(blob, ".csv")
    assert list(frame.columns) == ["a", "b", "c"]
    assert len(frame) == 2


def test_headerless_with_numeric_last_column_uses_plain_names():
    """No label column -> no `target` name is invented."""
    blob = b"1,2,3\n4,5,6\n7,8,9\n"
    frame = load_dataframe(blob, ".csv")
    assert list(frame.columns) == ["column_1", "column_2", "column_3"]
    assert len(frame) == 3


def test_headerless_semicolon_file_also_recovers():
    blob = (
        "1,5;2,4;3,7;0,2;setosa\n"
        "4,9;3,0;1,3;0,1;setosa\n"
        "6,4;5,4;4,6;1,5;versicolor\n"
    ).encode()
    frame = load_dataframe(blob, ".csv")
    assert len(frame) == 3
    assert list(frame.columns)[-1] == "target"
