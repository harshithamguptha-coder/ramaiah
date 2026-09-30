"""CSV delimiter detection.

The UCI Wine Quality files are semicolon-delimited. A naive comma read collapses
the whole row into one column, which previously surfaced as the confusing
"fewer than two columns" warning. These tests pin the generic behaviour.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from utils.errors import ParseError
from utils.profiling import (
    CANDIDATE_DELIMITERS,
    _candidate_delimiters,
    load_dataframe,
    profile_dataframe,
)

HEADER = [
    "fixed_acidity", "volatile_acidity", "citric_acid", "residual_sugar",
    "chlorides", "free_sulfur_dioxide", "total_sulfur_dioxide", "density",
    "pH", "sulphates", "alcohol", "quality",
]
ROWS = [
    ["7.4", "0.70", "0.00", "1.9", "0.076", "11", "34", "0.9978", "3.51", "0.56", "9.4", "5"],
    ["7.4", "0.88", "0.00", "2.6", "0.098", "25", "34", "0.9973", "3.52", "0.50", "9.0", "5"],
    ["7.3", "0.62", "0.00", "1.9", "0.088", "15", "40", "0.9967", "3.46", "0.47", "9.5", "6"],
    ["6.2", "1.58", "0.16", "6.8", "0.068", "34", "124", "0.9938", "3.39", "1.82", "10.2", "4"],
]

DELIMITERS = [("comma", ","), ("semicolon", ";"), ("tab", "\t"), ("pipe", "|")]


def build(sep: str, rows=ROWS, header=HEADER) -> bytes:
    lines = [sep.join(header)] + [sep.join(r) for r in rows]
    return "\n".join(lines).encode()


# ---------------------------------------------------------------------------
# Every supported delimiter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "sep"), DELIMITERS)
def test_all_four_delimiters_parse_to_the_same_shape(name, sep):
    frame = load_dataframe(build(sep), ".csv")
    assert frame.shape == (4, 12), f"{name}-delimited file parsed as {frame.shape}"
    assert list(frame.columns) == HEADER


@pytest.mark.parametrize(("name", "sep"), DELIMITERS)
def test_all_four_delimiters_yield_a_full_profile(name, sep):
    profile = profile_dataframe(load_dataframe(build(sep), ".csv"), target_column="quality")
    assert profile["columns"] == 12
    assert profile["feature_count"] == 11
    assert profile["numerical_features"] == 12
    assert profile["target_column"] == "quality"
    # The "fewer than two columns" warning must never appear now.
    assert not any("fewer than two columns" in w for w in profile["warnings"])


def test_semicolon_is_the_real_wine_quality_case():
    """The regression that prompted this: ';' with 12 columns."""
    frame = load_dataframe(build(";"), ".csv")
    assert frame.shape[1] == 12
    assert "quality" in frame.columns
    assert frame["quality"].nunique() == 3  # values present in ROWS


def test_candidate_order_prefers_the_real_delimiter():
    for _name, sep in DELIMITERS:
        assert _candidate_delimiters(build(sep).decode())[0] == sep


def test_european_semicolon_with_comma_decimals():
    """A ';' file using ',' decimals must still produce numeric columns."""
    blob = (
        "fixed_acidity;volatile_acidity;citric_acid;quality\n"
        "7,4;0,70;0,00;5\n7,3;0,62;0,09;6\n6,2;1,58;0,16;4\n"
    ).encode()
    frame = load_dataframe(blob, ".csv")
    assert frame.shape == (3, 4)
    assert len(frame.select_dtypes("number").columns) == 4, frame.dtypes.to_dict()


def test_comma_file_does_not_regress():
    """The overwhelmingly common case must keep working exactly as before."""
    frame = load_dataframe(build(","), ".csv")
    assert frame.shape == (4, 12)
    assert frame["fixed_acidity"].dtype.kind == "f"


# ---------------------------------------------------------------------------
# Validation is kept, not removed
# ---------------------------------------------------------------------------


def test_single_column_file_is_rejected_with_an_actionable_message():
    """After every delimiter is tried, a 1-column file is still invalid."""
    with pytest.raises(ParseError) as excinfo:
        load_dataframe(b"alpha\nbeta\ngamma\n", ".csv")
    message = excinfo.value.message
    assert "single column" in message
    # The message must tell the user which delimiters were attempted.
    for _name, sep in DELIMITERS:
        assert repr(sep)[1:-1] in message or sep in message or sep.replace("\t", "\\t") in message


def test_parse_error_details_report_the_delimiters_tried():
    with pytest.raises(ParseError) as excinfo:
        load_dataframe(b"alpha\nbeta\n", ".csv")
    details = excinfo.value.details
    assert details["reason"] == "single_column"
    assert set(details["delimiters_tried"]) <= set(CANDIDATE_DELIMITERS)


def test_empty_file_still_reports_empty_not_single_column():
    with pytest.raises(Exception) as excinfo:
        load_dataframe(b"", ".csv")
    assert "empty" in str(excinfo.value).lower()


def test_candidate_delimiters_never_empty():
    """The ranked guess is first; every supported delimiter is always covered."""
    assert _candidate_delimiters("a,b\n1,2\n")[0] == ","
    # A file with no candidate character still gets the full set attempted.
    assert set(_candidate_delimiters("alpha\nbeta\n")) == set(CANDIDATE_DELIMITERS)

