"""Dataset ingestion and structural profiling (real).

This module turns an uploaded file into a ``pandas.DataFrame`` and then computes
the structural facts the rest of the engine reasons about:

* rows / columns, numerical vs categorical split
* missing cells, duplicated rows
* per-column cardinality and id-like (high-cardinality) columns
* feature-to-sample ratio and the 2**d feature-selection search space
* class distribution, when a target column can be resolved
* in-memory size

Design notes
------------
**Row budget.** Profiling reads at most ``settings.analysis_max_rows`` rows.
Larger files are sampled deterministically (head + tail) and the result is
flagged ``sampled``. Sampling keeps a request bounded in wall-clock time instead
of streaming a multi-GB CSV into memory.

**Never crash the upload.** ``load_dataframe`` raises typed errors (the caller
decides whether that is fatal), while ``profile_dataset`` degrades to a flagged
empty profile so the *upload* itself still succeeds. A dataset that cannot be
parsed is a fact about the analysis, not a reason to 500 on ingest.

**Back-compat.** ``profile_dataset(content, extension, file_size)`` keeps the
signature the prototype used, so any other caller keeps working.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import settings
from utils.errors import EmptyDatasetError, ParseError, UnsupportedFileTypeError
from utils.logging_config import get_logger

logger = get_logger(__name__)

# Column names that strongly imply a supervised label.
_TARGET_HINTS = (
    "target", "label", "class", "y", "outcome", "result", "status", "churn",
    "is_", "has_", "fraud", "default", "prediction", "dependent", "response",
)

# Words in a problem statement that indicate an optimisation / search framing.
OPTIMIZATION_HINTS = (
    "optimis", "optimiz", "minimi", "maximi", "combinatorial", "scheduling",
    "schedule", "route", "routing", "assignment", "portfolio", "knapsack",
    "allocation", "planning", "constraint", "packing", "tsp",
    "vehicle routing", "feature selection", "subset selection", "subset",
)

CLASSIFICATION_HINTS = (
    "classif", "categor", "label", "churn", "fraud", "detect", "spam",
    "diagnos", "identif", "segment", "discret", "binary", "multiclass",
    "predict whether", "yes or no",
)

REGRESSION_HINTS = (
    "regress", "estimate", "predict the value", "forecast", "price", "revenue",
    "sales", "demand", "temperature", "continuous", "predict a number",
    "how much", "how many",
)

CLUSTERING_HINTS = (
    "cluster", "segmentation", "group similar", "anomaly", "outlier",
    "unsupervised", "customer segmentation", "grouping",
)


#: Words that name a label in a supervised tabular dataset. This is a
#: *vocabulary*, not a list of known datasets: any column whose normalised name
#: is (or contains, as a whole word) one of these is a strong target candidate.
TARGET_NAME_VOCABULARY = frozenset({
    # generic ML naming
    "target", "label", "class", "y", "outcome", "result", "prediction",
    "response", "dependent", "groundtruth", "answer",
    # domain words that name a label rather than a measurement
    "survived", "survival", "death", "dead", "diagnosis", "disease", "cancer",
    "species", "quality", "churn", "churned", "default", "fraud", "spam",
    "sentiment", "healthy", "defect", "failure", "approved", "accepted",
    "paid", "billing", "resolved", "closed", "returned", "purchased",
    "malignant", "benign", "positive", "negative",
})

#: Vocabulary words distinctive enough to also be matched *inside* a compound
#: name (`survival_status`, `is_malignant`). Generic words such as "score" are
#: deliberately excluded, so a feature called `risk_score` is not mistaken for
#: the label.
_LABEL_SUBSTRING_WORDS = frozenset({
    "survived", "survival", "death", "diagnosis", "disease", "cancer",
    "species", "churn", "fraud", "spam", "sentiment", "defect", "failure",
    "quality",
})

#: Prefixes and suffixes that mark a label column.
_TARGET_PATTERNS = (
    "target", "label", "class", "outcome", "result", "prediction", "response",
    "is", "has", "was", "did", "can", "should", "y",
)

#: Patterns too short to be safe as a *suffix*: a bare "y" would match
#: "priority" or "quality", which are features, not labels.
_SHORT_PATTERNS = frozenset({"is", "y"})

#: Column names that identify a row rather than describe it. Never a target.
_IDENTIFIER_WORDS = frozenset({
    "id", "uuid", "guid", "name", "names", "ticket", "code", "index", "no",
    "number", "num", "key", "passengerid", "customerid", "orderid", "rowid",
    "email", "phone", "address", "url", "filename", "path",
})

# A column only becomes a target on description evidence alone if it is
# label-shaped; this is the floor for accepting a detection.
TARGET_ACCEPT_THRESHOLD = 40


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

#: Delimiters the sniffer is allowed to choose between.
CANDIDATE_DELIMITERS = (",", ";", "\t", "|")

#: How much of the file to inspect when guessing the delimiter.
SNIFF_BYTES = 64 * 1024
#: How many lines to compare when scoring a candidate delimiter.
SNIFF_LINES = 20

_DELIMITER_NAMES = {",": "comma (,)", ";": "semicolon (;)", "\t": "tab (\\t)", "|": "pipe (|)"}


def _as_buffer(source: Any) -> Any:
    """Return something pandas can read from.

    pandas 3 no longer accepts raw ``bytes`` for ``read_csv``/``read_excel``, so
    bytes are wrapped in a binary buffer. Paths and existing file-like objects
    are passed through untouched.
    """
    if isinstance(source, bytes | bytearray):
        return io.BytesIO(bytes(source))
    return source


def _head_text(source: Any) -> str:
    """Read the first chunk of a file as text without consuming a stream."""
    if isinstance(source, (str, Path)):
        try:
            with open(source, "rb") as handle:
                raw = handle.read(SNIFF_BYTES)
        except OSError:
            return ""
    elif isinstance(source, (bytes, bytearray)):
        raw = bytes(source)[:SNIFF_BYTES]
    else:
        position = source.tell() if hasattr(source, "tell") else None
        raw = source.read(SNIFF_BYTES)
        if position is not None and hasattr(source, "seek"):
            source.seek(position)

    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _candidate_delimiters(head: str) -> list[str]:
    """Rank plausible delimiters for a CSV, most likely first.

    ``csv.Sniffer`` is quote-aware but often gives up on ragged or unusual
    files, so it is only the first vote. The fallback counts each candidate
    across several lines and prefers the one that appears the *same number of
    times on every line* - which is what actually distinguishes a real
    delimiter from a stray character inside a field.
    """
    lines = [line for line in head.splitlines() if line.strip()][:SNIFF_LINES]
    if not lines:
        return list(CANDIDATE_DELIMITERS)

    ranked: list[tuple[float, str]] = []
    try:
        sniffed = csv.Sniffer().sniff(
            head[:SNIFF_BYTES], delimiters="".join(CANDIDATE_DELIMITERS)
        )
        if sniffed.delimiter in CANDIDATE_DELIMITERS:
            ranked.append((float(len(CANDIDATE_DELIMITERS) ** 3), sniffed.delimiter))
    except csv.Error:
        pass

    for delimiter in CANDIDATE_DELIMITERS:
        counts = [line.count(delimiter) for line in lines]
        if not counts or max(counts) == 0:
            continue
        consistency = sum(1 for c in counts if c == counts[0]) / len(counts)
        ranked.append((counts[0] * consistency, delimiter))

    if not ranked:
        return list(CANDIDATE_DELIMITERS)

    ranked.sort(key=lambda item: -item[0])
    ordered: list[str] = [d for _, d in ranked]
    ordered += [d for d in CANDIDATE_DELIMITERS if d not in ordered]
    return ordered


def _parse_quality(frame: pd.DataFrame) -> tuple[int, int, int]:
    """Score a candidate parse: (columns, rows, numeric columns)."""
    return (
        int(frame.shape[1]),
        int(len(frame)),
        int(frame.select_dtypes("number").shape[1]),
    )


def _parses_as_number(value: Any) -> bool:
    """Would this string read back as a number?"""
    try:
        float(str(value).strip().replace(",", "."))
        return True
    except (TypeError, ValueError):
        return False


def _header_looks_like_data(frame: pd.DataFrame) -> bool:
    """Do the column *names* actually look like data values?"""
    if frame.shape[1] < 2:
        return False
    names = [str(c).strip() for c in frame.columns]
    numeric_like = sum(1 for name in names if _parses_as_number(name))
    return numeric_like > len(names) / 2


def _recover_headerless(
    source: Any, delimiter: str, decimal: str, frame: pd.DataFrame
) -> pd.DataFrame:
    """Re-read a headerless CSV and give the columns usable names.

    A non-numeric final column with numeric columns before it is named
    ``feature_1 .. feature_{n-1}`` + ``target``; anything else becomes
    ``column_1 .. column_n``.
    """
    try:
        raw = pd.read_csv(
            _as_buffer(source), sep=delimiter, decimal=decimal, header=None,
            low_memory=False, skipinitialspace=True,
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError):
        return frame

    raw = raw.dropna(axis=1, how="all")
    if raw.shape[1] < 2 or len(raw) == 0:
        return frame

    n_cols = raw.shape[1]
    last_is_label = not pd.api.types.is_numeric_dtype(raw.iloc[:, -1])
    others_numeric = sum(
        1 for i in range(n_cols - 1) if pd.api.types.is_numeric_dtype(raw.iloc[:, i])
    )
    if last_is_label and others_numeric >= 1:
        names = [f"feature_{i + 1}" for i in range(n_cols - 1)] + ["target"]
    else:
        names = [f"column_{i + 1}" for i in range(n_cols)]
    raw.columns = names
    logger.info("Headerless CSV recovered: %d row(s) restored", len(raw))
    return raw


def _read_csv(source: Any) -> pd.DataFrame:
    """Read a CSV, detecting its delimiter instead of assuming a comma."""
    head = _head_text(source)
    if not head.strip():
        raise ParseError(
            "The CSV file is empty - it has no header row and no data.",
            details={"reason": "empty_data"},
        )

    candidates = _candidate_delimiters(head)
    attempts: list[tuple[str, str]] = []
    for delimiter in candidates:
        attempts.append((delimiter, "."))
        if delimiter != ",":
            attempts.append((delimiter, ","))

    best_frame: pd.DataFrame | None = None
    best_key: tuple[int, int, int] | None = None
    best_choice: tuple[str, str] | None = None

    for delimiter, decimal in attempts:
        try:
            frame = pd.read_csv(
                _as_buffer(source), sep=delimiter, decimal=decimal,
                low_memory=False, skipinitialspace=True,
            )
        except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError, ValueError):
            continue
        key = _parse_quality(frame)
        if best_key is None or key > best_key:
            best_frame, best_key, best_choice = frame, key, (delimiter, decimal)

    if best_frame is None or best_key[0] <= 1:
        for delimiter, _ in attempts[:1]:
            try:
                frame = pd.read_csv(
                    _as_buffer(source), sep=delimiter, low_memory=False,
                    skipinitialspace=True, encoding="latin-1",
                )
            except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError):
                continue
            key = _parse_quality(frame)
            if best_key is None or key > best_key:
                best_frame, best_key, best_choice = frame, key, (delimiter, ".")
            break

    if best_frame is None:
        raise ParseError(
            "The CSV file could not be parsed with any of the supported delimiters "
            f"({', '.join(_DELIMITER_NAMES[d] for d in candidates)}).",
            details={"reason": "csv_parser_error", "delimiters_tried": list(candidates)},
        )

    delimiter, decimal = best_choice
    logger.info(
        "CSV parsed: delimiter=%s decimal=%r rows=%d columns=%d numeric_columns=%d",
        _DELIMITER_NAMES.get(delimiter, repr(delimiter)), decimal,
        best_key[1], best_key[0], best_key[2],
    )

    if _header_looks_like_data(best_frame):
        recovered = _recover_headerless(source, delimiter, decimal, best_frame)
        if len(recovered) > len(best_frame):
            best_frame = recovered

    if best_key[0] <= 1:
        raise ParseError(
            "The file was read as a single column with every supported delimiter "
            f"({', '.join(_DELIMITER_NAMES[d] for d in CANDIDATE_DELIMITERS)}), so no "
            "features could be derived. Check that the file is really a delimited table.",
            details={"reason": "single_column", "columns_detected": best_key[0],
                     "delimiters_tried": list(CANDIDATE_DELIMITERS)},
        )
    return best_frame


def _read_xlsx(source: Any) -> pd.DataFrame:
    """Read the first worksheet of an XLSX workbook."""
    try:
        return pd.read_excel(_as_buffer(source), engine="openpyxl")
    except ImportError as exc:  # pragma: no cover
        raise UnsupportedFileTypeError(
            "XLSX support requires the 'openpyxl' package.", details={"extension": ".xlsx"}
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ParseError(
            "The XLSX file could not be read. It may be corrupt, password protected, or "
            "use an unsupported feature. Re-saving it as CSV also works.",
            details={"reason": "xlsx_read_error", "error_type": type(exc).__name__},
        ) from exc


def _read_json(source: Any, nrows: int | None) -> pd.DataFrame:
    """Read JSON as a list of records, {"data": [...]}, or NDJSON."""
    if isinstance(source, (str, Path)):
        text = Path(source).read_text(encoding="utf-8-sig", errors="replace")
    elif isinstance(source, bytes):
        text = source.decode("utf-8-sig", errors="replace")
    else:
        text = source.read().decode("utf-8-sig", errors="replace")

    text = text.strip()
    if not text:
        raise ParseError("The JSON file is empty.", details={"reason": "empty_file"})

    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        try:
            payload = [json.loads(line) for line in text.splitlines() if line.strip()]
        except json.JSONDecodeError as exc:
            raise ParseError(
                "The JSON file is neither valid JSON nor newline-delimited JSON.",
                details={"reason": "json_decode_error", "parser_message": str(exc)[:300]},
            ) from exc

    if isinstance(payload, dict):
        for key in ("data", "records", "rows", "items"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            payload = [payload]
    elif not isinstance(payload, list):
        payload = [{"value": payload}]

    records = [r for r in payload if isinstance(r, dict)]
    if not records:
        raise ParseError(
            "No usable records were found in the JSON file. Expected a list of objects, "
            "or an object containing a 'data' list.",
            details={"reason": "no_records"},
        )
    frame = pd.DataFrame(records)
    if nrows is not None and len(frame) > nrows:
        frame = frame.head(nrows)
    return frame


def _deduplicate(names: list[str]) -> list[str]:
    """Return names with duplicates disambiguated by a ``_2``-style suffix."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for name in names:
        if name not in seen:
            seen[name] = 0
            out.append(name)
            continue
        seen[name] += 1
        out.append(f"{name}_{seen[name] + 1}")
    return out


def head_tail_sample(frame: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    """Deterministically keep at most ``max_rows`` rows, preserving both ends."""
    if len(frame) <= max_rows:
        return frame
    head = max_rows // 2
    tail = max_rows - head
    return pd.concat([frame.head(head), frame.tail(tail)]).drop_duplicates(ignore_index=True)


def normalise_frame(frame: pd.DataFrame, *, max_rows: int | None = None) -> pd.DataFrame:
    """Clean column names, drop fully-empty columns and bound the row count."""
    frame = frame.copy()
    frame.columns = _deduplicate(
        [str(c).strip() or f"column_{i + 1}" for i, c in enumerate(frame.columns)]
    )
    empty = [c for c in frame.columns if frame[c].isna().all()]
    if empty:
        frame = frame.drop(columns=empty)

    if max_rows is not None and len(frame) > max_rows:
        sampled = head_tail_sample(frame, max_rows)
        sampled.attrs["sampled"] = True
        return sampled
    frame.attrs["sampled"] = False
    return frame


def column_kind(series: pd.Series) -> str:
    """Classify a column as numerical, categorical or datetime."""
    if pd.api.types.is_bool_dtype(series):
        return "categorical"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numerical"
    return "categorical"


def _class_distribution(series: pd.Series) -> tuple[dict[str, int], int]:
    """Return ``({label: count}, n_classes)`` for a candidate target column."""
    counts = series.value_counts(dropna=True)
    n_classes = int(counts.shape[0])
    distribution = {str(idx): int(val) for idx, val in counts.head(25).items()}
    if n_classes > 25:
        distribution["__other__"] = int(counts.iloc[25:].sum())
    return distribution, n_classes


def load_dataframe(source: Any, extension: str, *, nrows: int | None = None) -> pd.DataFrame:
    """Load an uploaded file into a DataFrame.

    Raises a typed :class:`~utils.errors.AnalysisError` subclass for anything
    unreadable.
    """
    ext = (extension or "").lower()
    limit = nrows if nrows is not None else settings.analysis_max_rows

    if ext == ".csv":
        frame = _read_csv(source)
    elif ext == ".xlsx":
        frame = _read_xlsx(source)
    elif ext == ".json":
        frame = _read_json(source, limit)
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{ext or 'unknown'}'. "
            f"Allowed types: {', '.join(settings.allowed_extensions)}",
            details={"extension": ext},
        )

    if len(frame) == 0:
        raise EmptyDatasetError(
            "The file contains column headers but no data rows.",
            details={"reason": "no_rows", "columns": int(frame.shape[1])},
        )
    frame = normalise_frame(frame, max_rows=limit)
    if frame.shape[1] == 0:
        raise ParseError(
            "The file parsed successfully but contains no usable columns.",
            details={"reason": "no_columns"},
        )
    return frame


def normalise_name(column: Any) -> str:
    """Lowercase, strip punctuation and drop a plural ``s``.

    ``Survived`` / ``survived`` / ``SURVIVED`` all normalise to ``survived``;
    ``Classes`` normalises to ``classe``, which still matches the ``class``
    pattern, so the pattern check is done on the un-singularised form too.
    """
    text = re.sub(r"[^a-z0-9]+", " ", str(column).lower()).strip()
    return text


def _singular(word: str) -> str:
    # Past/participle endings first, so "churned" reduces to "churn".
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return word[: -len(suffix)]
    for suffix in ("sses", "ses", "xes", "ies", "es", "s"):
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            base = word[: -len(suffix)]
            if suffix == "ies":
                return base + "y"
            if suffix in ("sses", "ses", "xes", "es"):
                return word[: -len(suffix) - 1] if suffix != "es" else word[:-2]
            return base
    return word


_STOPWORDS = frozenset({
    "the", "a", "an", "of", "for", "to", "and", "or", "is", "are", "was", "were",
    "be", "been", "from", "with", "this", "that", "will", "would", "can", "could",
    "predict", "prediction", "determine", "given", "based", "using", "use", "data",
    "dataset", "model", "value", "values", "each", "row", "record", "whether", "if",
})


#: Phrases that signal "predict this number", which lets the description point
#: at a continuous target column (a regression task).
_REGRESSION_FRAMING = frozenset({
    "estimate", "predict", "forecast", "regress", "projection", "predicting",
    "expected", "value", "amount", "price", "revenue", "score",
})


def _significant_words(text: str) -> set[str]:
    """Content words of a phrase, lightly stemmed, used to compare names."""
    words = set()
    for token in re.split(r"[^a-z0-9]+", text.lower()):
        if len(token) < 4 or token in _STOPWORDS:
            continue
        words.add(token)
        words.add(_singular(token))
    return words


def _matches_target_pattern(name: str) -> bool:
    """Prefix/suffix test, run on the singular form as well.

    Short patterns are only accepted as a *prefix*, because as a suffix they
    produce false positives ("priority" ends in "y").
    """
    candidates = {name, _singular(name)}
    for candidate in candidates:
        for pattern in _TARGET_PATTERNS:
            if candidate.startswith(pattern):
                return True
            if len(pattern) > 2 and candidate.endswith(pattern):
                return True
    return False


def _identifier_like(name: str) -> bool:
    """Does the name read as a row identifier rather than a measurement?"""
    normalised = name.replace(" ", "")
    if normalised in _IDENTIFIER_WORDS:
        return True
    words = set(normalised.split())
    return bool(words & _IDENTIFIER_WORDS) and len(words) <= 2


def _name_vocabulary_score(name: str, compact: str) -> int:
    """Does the column name contain a standard label word?

    Equality is strong (100); containment is also strong but weaker, because
    compound names are common (``is_churned`` contains ``churn``). Containment
    is what lets `Survived`, `survival_status` and `passenger_survived` all
    count without any of them being hard-coded.
    """
    if compact in TARGET_NAME_VOCABULARY or _singular(compact) in TARGET_NAME_VOCABULARY:
        return 100
    words = [w for w in name.split() if w]
    for word in words + [_singular(w) for w in words]:
        if word in TARGET_NAME_VOCABULARY:
            return 100
    if compact in TARGET_NAME_VOCABULARY or _singular(compact) in TARGET_NAME_VOCABULARY:
        return 100
    # Compound names without separators: "ischurned" contains "churn". Only
    # distinctive words are used here, never generic ones.
    for word in _LABEL_SUBSTRING_WORDS:
        if len(word) > 3 and word in compact:
            return 90
    return 0


def score_target_candidates(
    frame: pd.DataFrame, description: str = ""
) -> list[dict[str, Any]]:
    """Rank every column by how likely it is to be the target.

    Three independent kinds of evidence are combined, so detection does not
    depend on a column being literally called ``target``:

    * **name** - a standard label word in :data:`TARGET_NAME_VOCABULARY`
      (strong), or a label prefix/suffix such as ``is_``/``_class`` (moderate);
    * **description** - the problem statement naming the column
      ("Predict whether a passenger *survived*" -> the ``Survived`` column);
    * **shape** - a small nudge only. A column merely having few values is *not*
      evidence of being a label, because ``Pclass``, ``Embarked`` and
      ``duration`` all have few values too.

    A column is only ever selected on **name or description** evidence, so a
    dataset with no label is still reported as unsupervised instead of having a
    random low-cardinality feature promoted to a target.
    """
    rows = int(len(frame))
    described = _significant_words(description or "")
    candidates: list[dict[str, Any]] = []

    for column in frame.columns:
        name = normalise_name(column)
        compact = name.replace(" ", "")
        series = frame[column]
        distinct = int(series.nunique(dropna=True))
        kind = column_kind(series)
        reasons: list[str] = []
        name_score = _name_vocabulary_score(name, compact)
        desc_score = 0
        shape_score = 0

        if name_score:
            reasons.append(f'"{column}" contains a standard label name.')
        elif _matches_target_pattern(compact):
            name_score = 40
            reasons.append(f'"{column}" uses a label naming pattern.')

        # A numeric column with 2 distinct values is a flag; with more it is
        # usually a measurement. Neither makes it a label on its own.
        categorical = kind == "categorical"
        label_shaped = categorical or (0 < distinct <= 20)
        if categorical:
            shape_score += 15
        elif 0 < distinct <= 20:
            shape_score += 5
        else:
            shape_score -= 8

        if described:
            overlap = described & _significant_words(name)
            if overlap and name_score:
                desc_score += 60
                reasons.append(
                    f'The problem statement mentions it ("{", ".join(sorted(overlap))}").'
                )
            elif overlap and label_shaped:
                desc_score += 60
                reasons.append(
                    f'The problem statement mentions it ("{", ".join(sorted(overlap))}") '
                    "and it is label-shaped."
                )
            elif overlap and _REGRESSION_FRAMING & described:
                # "Estimate the sale price" names a continuous column to predict.
                desc_score += 60
                reasons.append(
                    f'The problem statement asks for this quantity to be predicted '
                    f'("{" , ".join(sorted(overlap))}").'
                )

        if _identifier_like(compact):
            shape_score -= 60
            reasons.append(f'"{column}" reads as a row identifier, not a label.')
        near_unique = bool(rows) and distinct > 20 and distinct >= rows * 0.95
        if near_unique and (categorical or _identifier_like(compact)):
            # Free text or an id: uniqueness means it identifies a row.
            shape_score -= 200
            reasons.append(f'"{column}" is unique per row, so it cannot be a label.')

        # Description evidence may not promote a non-label-shaped column alone.
        numeric_prediction = bool(kind == "numerical" and _REGRESSION_FRAMING & described)
        if name_score == 0 and desc_score > 0 and not (label_shaped or numeric_prediction):
            desc_score = 0
            reasons = [r for r in reasons if "problem statement" not in r]

        total = name_score + desc_score + shape_score
        # Never select on shape alone: this is what keeps a genuinely
        # unsupervised dataset from being given an invented label.
        if total <= 0 or (name_score == 0 and desc_score == 0):
            continue
        candidates.append(
            {
                "column": column,
                "score": int(total),
                "name_score": name_score,
                "description_score": desc_score,
                "shape_score": shape_score,
                "label_shaped": label_shaped,
                "distinct_values": distinct,
                "reasons": reasons,
            }
        )

    candidates.sort(key=lambda item: -item["score"])
    return candidates


def resolve_target(
    frame: pd.DataFrame,
    requested: str | None = None,
    description: str = "",
) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    """Return ``(target_column, source, ranked_candidates)``.

    A caller-supplied target always wins. Otherwise the highest-scoring
    candidate above :data:`TARGET_ACCEPT_THRESHOLD` is used. The source records
    which evidence decided it, so the UI can say *why* a column was chosen.
    """
    candidates = score_target_candidates(frame, description)

    if requested:
        if requested in frame.columns:
            return requested, "user-specified", candidates
        logger.warning("Requested target column %r is not in the dataset", requested)

    if not candidates:
        return None, None, candidates

    best = candidates[0]
    if best["score"] < TARGET_ACCEPT_THRESHOLD:
        return None, None, candidates

    if best["description_score"] > best["name_score"]:
        source = "inferred from the problem statement"
    else:
        source = "inferred from the column name"
    return best["column"], source, candidates


def looks_like_classification_target(series: pd.Series) -> bool:
    """Heuristic: is this target a label rather than a continuous measure?"""
    kind = column_kind(series)
    clean = series.dropna()
    n_unique = int(clean.nunique())
    if n_unique <= 1:
        return False
    if kind == "categorical":
        return True
    if kind == "numerical":
        # Low-cardinality integer columns (labels encoded 0/1/2/...) are classes.
        return bool(n_unique <= 20 and np.allclose(clean.astype(float) % 1, 0))
    return False


def size_label_for(size_mb: float) -> str:
    """Human size bucket used by the classical resource estimate."""
    if size_mb < 1:
        return "Tiny (<1 MB)"
    if size_mb < 10:
        return "Small (<10 MB)"
    if size_mb < 100:
        return "Medium (10-100 MB)"
    return "Large (>100 MB)"


def profile_dataframe(
    frame: pd.DataFrame,
    *,
    target_column: str | None = None,
    file_size_bytes: int = 0,
    source_label: str = "pandas",
    description: str = "",
) -> dict[str, Any]:
    """Compute the full structural profile of a DataFrame.

    Returns a JSON-serialisable dict: the shape facts the prototype already
    exposed (``rows``, ``numerical_features``, ``missing_values``, ...) plus the
    deeper statistics the decision engine needs (cardinality, duplicates, class
    balance, feature-selection search space).
    """
    rows = int(len(frame))
    columns = [str(c) for c in frame.columns]
    n_cols = len(columns)

    kinds = {c: column_kind(frame[c]) for c in frame.columns}
    numerical = [c for c in columns if kinds[c] == "numerical"]
    categorical = [c for c in columns if kinds[c] == "categorical"]
    datetimes = [c for c in columns if kinds[c] == "datetime"]

    missing_values = int(frame.isna().sum().sum())
    total_cells = rows * n_cols
    missing_percent = round(missing_values / total_cells * 100, 2) if total_cells else 0.0
    duplicate_rows = int(frame.duplicated().sum())

    # Cardinality per column, computed on a bounded sample for speed.
    cardinality_sample = frame.head(min(rows, 5_000) or rows)
    cardinality = {c: int(cardinality_sample[c].nunique(dropna=True)) for c in columns}

    target, target_source, target_candidates = resolve_target(
        frame, target_column, description
    )
    features = [c for c in columns if c != target] if target else columns

    high_cardinality = [
        c
        for c in features
        if rows and cardinality.get(c, 0) > rows * settings.analysis_high_cardinality_ratio
    ]
    id_like = [
        c
        for c in features
        if rows and cardinality.get(c, 0) > 20 and cardinality.get(c, 0) >= rows * 0.95
    ]

    class_distribution: dict[str, int] | None = None
    class_count: int | None = None
    problem_type = "unknown"
    if target and target in frame.columns:
        series = frame[target]
        if column_kind(series) == "categorical":
            # A non-numeric target is a label by definition. This deliberately
            # includes the degenerate single-class case, which is *not* a
            # regression target and must be reported as a classification problem
            # that cannot be evaluated - not silently sent to a regressor.
            class_distribution, class_count = _class_distribution(series)
            problem_type = "classification"
        elif looks_like_classification_target(series):
            class_distribution, class_count = _class_distribution(series)
            problem_type = "classification"
        else:
            problem_type = "regression"

    n_features = len(features)
    memory_mb = round(float(frame.memory_usage(deep=True).sum()) / (1024 * 1024), 3)
    size_mb = round((file_size_bytes or 0) / (1024 * 1024), 3)

    warnings: list[str] = []
    if rows == 0:
        warnings.append("The dataset contains no rows.")
    if n_cols <= 1:
        # Reached only when a frame is built directly (a single-column file is
        # rejected during loading, after every delimiter has been tried).
        warnings.append(
            "The dataset has a single column, so no features can be derived. If this file "
            "is a delimited table, check that its delimiter is one of: "
            + ", ".join(_DELIMITER_NAMES.get(d, d) for d in CANDIDATE_DELIMITERS)
            + "."
        )
    if duplicate_rows:
        # Data-quality information only - duplicates never stop the pipeline.
        share = round(duplicate_rows / rows * 100, 2)
        noun = "row" if duplicate_rows == 1 else "rows"
        warnings.append(
            f"{duplicate_rows:,} duplicate {noun} detected ({share}% of the data). "
            "Reported as a data-quality note; the analysis continues."
        )
    if missing_percent > 40:
        warnings.append(f"{missing_percent}% of all cells are missing.")
    if not target:
        warnings.append("No target column was detected - supervised evaluation will be skipped.")
    if getattr(frame, "attrs", {}).get("sampled"):
        warnings.append(
            f"Only the first and last {rows:,} rows were read; the file is larger than the "
            "configured analysis budget, so statistics describe this sample."
        )

    return {
        "rows": rows,
        "columns": n_cols,
        "column_names": columns,
        "numerical_features": len(numerical),
        "categorical_features": len(categorical),
        "datetime_features": len(datetimes),
        "numerical_columns": numerical,
        "categorical_columns": categorical,
        "feature_names": features,
        "feature_count": n_features,
        "missing_values": missing_values,
        "missing_percent": missing_percent,
        "columns_with_missing": int((frame.isna().sum() > 0).sum()),
        "duplicate_rows": duplicate_rows,
        "duplicate_percent": round(duplicate_rows / rows * 100, 2) if rows else 0.0,
        "target_column": target,
        "target_source": target_source,
        "target_candidates": target_candidates[:5],
        "class_distribution": class_distribution,
        "class_count": class_count,
        "feature_cardinality": cardinality,
        "mean_cardinality": (
            round(sum(cardinality.get(c, 0) for c in features) / n_features, 2) if n_features else 0.0
        ),
        "high_cardinality_features": high_cardinality[:20],
        "id_like_features": id_like[:20],
        "feature_to_sample_ratio": round(n_features / rows, 4) if rows else None,
        "estimated_search_space": 2**n_features if n_features <= 512 else None,
        "estimated_search_space_log2": float(n_features),
        "dataset_size_bytes": int(file_size_bytes),
        "dataset_size_mb": size_mb,
        "size_label": size_label_for(size_mb),
        "memory_footprint_mb": memory_mb,
        "problem_type": problem_type,
        "profile_method": f"pandas ({source_label})",
        "sampled": bool(getattr(frame, "attrs", {}).get("sampled", False)),
        "warnings": warnings,
    }


def empty_profile(reason: str) -> dict[str, Any]:
    """A well-formed, fully-null profile used when parsing failed."""
    return {
        "rows": 0, "columns": 0, "column_names": [],
        "numerical_features": 0, "categorical_features": 0, "datetime_features": 0,
        "numerical_columns": [], "categorical_columns": [],
        "feature_names": [], "feature_count": 0,
        "missing_values": None, "missing_percent": None, "columns_with_missing": None,
        "duplicate_rows": None, "duplicate_percent": None,
        "target_column": None, "target_source": None, "target_candidates": [],
        "class_distribution": None, "class_count": None,
        "feature_cardinality": {}, "mean_cardinality": 0.0,
        "high_cardinality_features": [], "id_like_features": [],
        "feature_to_sample_ratio": None,
        "estimated_search_space": None, "estimated_search_space_log2": 0.0,
        "dataset_size_bytes": 0, "dataset_size_mb": 0.0,
        "size_label": "Unknown", "memory_footprint_mb": 0.0,
        "problem_type": "unknown",
        "profile_method": f"failed ({reason})",
        "sampled": False,
        "warnings": [f"Dataset could not be parsed ({reason})."],
    }


# --------------------------------------------------------------------------
# Back-compat entry point
# --------------------------------------------------------------------------


def profile_dataset(
    content: bytes,
    extension: str,
    file_size: int,
    *,
    target_column: str | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Return a structural profile for raw uploaded bytes.

    Never raises: a malformed file degrades to a flagged empty profile so the
    upload flow itself still succeeds. Used by the ingest path; the analysis
    stages prefer :func:`load_dataframe`, which also hands back the frame.
    """
    ext = (extension or "").lower()
    try:
        if not content:
            raise ParseError("Uploaded file is empty.", details={"reason": "empty_file"})
        if ext == ".csv":
            profile = profile_dataframe(
                load_dataframe(content, ext),
                target_column=target_column,
                file_size_bytes=file_size,
            )
        elif ext in (".xlsx", ".json"):
            profile = profile_dataframe(
                load_dataframe(content, ext),
                target_column=target_column,
                file_size_bytes=file_size,
            )
        else:
            raise UnsupportedFileTypeError(
                "Unsupported file type: " + (ext or "unknown") + ".",
                details={"extension": ext},
            )
    except Exception as exc:  # noqa: BLE001 - profiling must never break upload
        logger.warning("Profiling failed for %s: %s", ext, exc)
        profile = empty_profile(type(exc).__name__)

    # Legacy alias: the prototype used `columns` for the *list* of names.
    profile["columns_data"] = profile.get("column_names") or []
    return profile
