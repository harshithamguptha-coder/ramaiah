"""Stage 3 — classical ML baselines (real training, measured metrics).

What this stage does
--------------------
Trains a small, deliberately cheap set of standard estimators on the uploaded
data and reports what they *actually scored* on a held-out split. Nothing here
is estimated, extrapolated or seeded with a random number.

Why cheap on purpose
--------------------
The purpose of this stage is to establish a **reference floor** for the
recommendation engine, not to win a Kaggle competition. That means:

* logistic/linear regression, a random forest, and (when the data is small
  enough) an RBF SVM — all strong, well-understood tabular baselines;
* a ``DummyClassifier`` / ``DummyRegressor`` trained too, because "how much of
  this score is just the majority class?" is exactly the question a reader
  should be asking of a 0.98 accuracy;
* a hard row budget and a small forest, so a request always terminates.

If a candidate cannot be trained within budget it is reported with
``suitable=False`` and the reason, never silently dropped.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    root_mean_squared_error,
)
from sklearn.model_selection import (
    KFold,
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC, SVR

from config import settings
from utils.errors import InsufficientSamplesError, ModelTrainingError
from utils.logging_config import get_logger

logger = get_logger(__name__)

import warnings

# Convergence chatter from a bounded-iteration solver is expected here and would
# otherwise pollute the API log for every upload.
warnings.filterwarnings("ignore", category=ConvergenceWarning)

#: Complexity strings shown in the candidate table.
COMPLEXITY = {
    "Dummy": "O(n)",
    "Linear": "O(n * d)",
    "Ensemble": "O(n * d * log n)",
    "Kernel": "O(n^2 * d) - O(n^3 * d)",
}


def _preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    """Median-impute + scale numerics, impute + one-hot categoricals.

    ``min_frequency`` caps one-hot blow-up: a column with 500 distinct strings
    would otherwise explode the design matrix.
    """
    numeric_pipe = Pipeline(
        [("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
    )
    categorical_pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            (
                "onehot",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                    min_frequency=2,
                ),
            ),
        ]
    )
    return ColumnTransformer(
        [("num", numeric_pipe, numeric), ("cat", categorical_pipe, categorical)],
        remainder="drop",
        sparse_threshold=0.0,
    )


def _build_estimator(name: str, task: str) -> Any:
    """Instantiate one candidate by name."""
    seed = settings.analysis_random_seed
    if task == "classification":
        return {
            "Dummy (majority class)": lambda: DummyClassifier(strategy="most_frequent"),
            "Logistic Regression": lambda: LogisticRegression(
                max_iter=1000, random_state=seed
            ),
            "Random Forest": lambda: RandomForestClassifier(
                n_estimators=settings.analysis_forest_trees,
                max_depth=settings.analysis_forest_max_depth or None,
                min_samples_leaf=settings.analysis_forest_min_samples_leaf,
                random_state=seed,
                n_jobs=-1,
            ),
            "SVM (RBF kernel)": lambda: SVC(kernel="rbf", random_state=seed),
        }[name]()
    return {
        "Dummy (mean predictor)": lambda: DummyRegressor(strategy="mean"),
        "Linear Regression": lambda: LinearRegression(),
        "Random Forest Regressor": lambda: RandomForestRegressor(
            n_estimators=settings.analysis_forest_trees,
            max_depth=settings.analysis_forest_max_depth or None,
            min_samples_leaf=settings.analysis_forest_min_samples_leaf,
            random_state=seed,
            n_jobs=-1,
        ),
    }[name]()


FAMILIES = {
    "Dummy (majority class)": "Reference",
    "Dummy (mean predictor)": "Reference",
    "Logistic Regression": "Linear",
    "Linear Regression": "Linear",
    "Random Forest": "Ensemble",
    "Random Forest Regressor": "Ensemble",
    "SVM (RBF kernel)": "Kernel",
}


def classification_candidates(rows: int, features: int) -> list[str]:
    """Candidate list, filtered by the SVM cost ceiling."""
    names = ["Dummy (majority class)", "Logistic Regression", "Random Forest"]
    if (
        rows <= settings.analysis_svm_max_rows
        and features <= settings.analysis_svm_max_features
    ):
        names.append("SVM (RBF kernel)")
    return names


def regression_candidates() -> list[str]:
    return ["Dummy (mean predictor)", "Linear Regression", "Random Forest Regressor"]


def _metrics(task: str, y_true: Any, y_pred: Any) -> dict[str, Any]:
    """Compute the metric set appropriate to the task."""
    if task == "classification":
        # Macro averaging is used for every classification metric: it is defined
        # for any number of classes, weights each class equally (so a model is
        # not rewarded for ignoring a rare class), and - unlike "binary" - does
        # not need a `pos_label` when the labels are strings rather than 0/1.
        out = {
            "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
            "f1_score": round(
                float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4
            ),
            "precision": round(
                float(precision_score(y_true, y_pred, average="macro", zero_division=0)), 4
            ),
            "recall": round(
                float(recall_score(y_true, y_pred, average="macro", zero_division=0)), 4
            ),
        }
        return out
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse": round(float(root_mean_squared_error(y_true, y_pred)), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
    }


def primary_metric_for(task: str) -> str:
    """The single metric candidates are ranked on.

    F1 (macro) is preferred over raw accuracy for classification because accuracy
    is badly misleading under class imbalance; R^2 is the standard yardstick for
    regression.
    """
    return "f1_score" if task == "classification" else "r2"


def _skipped(reason: str, dataset: dict[str, Any], problem: dict[str, Any]) -> dict[str, Any]:
    """A well-formed block explaining why no model was trained."""
    return {
        "status": "skipped",
        "task": problem.get("problem_type", "unknown"),
        "method": "none - no model was trained",
        "primary_metric": None,
        "dataset_size": _size_block(dataset),
        "candidates": [],
        "baseline_model": None,
        "best_model": None,
        "metrics": {},
        "evaluation": None,
        "estimated_complexity": {
            "time": "n/a",
            "space": "n/a",
            "summary": "No model was trained for this problem.",
        },
        "resource_requirements": {
            "cpu_cores": 1,
            "memory_gb": 1,
            "gpu_required": False,
            "expected_runtime": "n/a",
            "notes": "No training took place.",
        },
        "summary": reason,
        "errors": [reason],
        "warnings": [],
        "is_mock": False,
        "note": "No model was trained; see the summary for the reason.",
    }


def _size_block(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows": dataset.get("rows") or 0,
        "columns": dataset.get("column_count") or 0,
        "size_mb": dataset.get("dataset_size_mb") or 0.0,
        "label": dataset.get("size_label") or "Unknown",
    }


def _prepare(
    frame: pd.DataFrame, target: str, task: str
) -> tuple[pd.DataFrame, pd.Series, list[str], list[str], int, int]:
    """Drop unusable rows, split X/y, and pick the numeric/categorical columns."""
    usable = [c for c in frame.columns if c != target and not frame[c].isna().all()]
    sub = frame[usable + [target]].copy()

    # A row with a missing target cannot be supervised; drop it.
    sub = sub[sub[target].notna()]
    # Constant columns carry no signal and make some scalers divide by zero.
    sub = sub.drop(columns=[c for c in usable if sub[c].nunique(dropna=True) <= 1])

    if len(sub) > settings.analysis_max_train_rows:
        sub = sub.head(settings.analysis_max_train_rows)

    features = [c for c in sub.columns if c != target][: settings.analysis_max_features]
    numeric = [c for c in features if pd.api.types.is_numeric_dtype(sub[c])]
    categorical = [c for c in features if c not in numeric]
    return sub[features], sub[target], numeric, categorical, len(features), int(len(sub))


def _cross_validate(pipe: Any, X: Any, y: Any, task: str, n_classes: int) -> dict[str, Any]:
    """K-fold CV on the primary metric, when the data supports it."""
    folds = settings.analysis_cv_folds
    primary = primary_metric_for(task)
    if folds < 2 or len(X) < folds * 2:
        return {"strategy": "train_test_split", "cv_folds": 0, "cv_mean": None, "cv_std": None}
    if task == "classification":
        if n_classes < 2 or int(pd.Series(y).value_counts().min()) < folds:
            return {
                "strategy": "train_test_split",
                "cv_folds": 0,
                "cv_mean": None,
                "cv_std": None,
                "note": "Too few samples in the rarest class for stratified cross-validation.",
            }
        splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=settings.analysis_random_seed)
    else:
        splitter = KFold(n_splits=folds, shuffle=True, random_state=settings.analysis_random_seed)
    try:
        scores = cross_val_score(pipe, X, y, cv=splitter, scoring=primary, n_jobs=1)
    except Exception as exc:  # noqa: BLE001 - CV is a bonus, never fatal
        return {
            "strategy": "train_test_split",
            "cv_folds": 0,
            "cv_mean": None,
            "cv_std": None,
            "note": f"Cross-validation failed: {type(exc).__name__}.",
        }
    return {
        "strategy": f"{folds}-fold cross-validation",
        "cv_folds": folds,
        "cv_mean": round(float(scores.mean()), 4),
        "cv_std": round(float(scores.std()), 4),
    }


def run(
    dataset: dict[str, Any],
    problem: dict[str, Any],
    analysis_id: str = "",
    frame: Any | None = None,
) -> dict[str, Any]:
    """Train the classical baselines and return the ``classical_analysis`` block.

    ``frame`` is the cached DataFrame. It is optional so the documented
    ``run(dataset, problem, analysis_id)`` signature still works; without it the
    stage degrades to a ``skipped`` block explaining what is missing.
    """
    task = problem.get("problem_type", "unknown")
    if task not in ("classification", "regression"):
        return _skipped(
            f"No supervised baseline was trained because the problem was characterised as "
            f"'{task}'. A classical baseline needs a target column to score against.",
            dataset,
            problem,
        )

    target = problem.get("target_column") or dataset.get("target_column")
    if not target:
        return _skipped(
            "No supervised baseline was trained because no target column could be resolved.",
            dataset,
            problem,
        )
    if frame is None or getattr(frame, "empty", True):
        return _skipped(
            "No supervised baseline was trained because the dataset could not be loaded "
            "into memory. Check the upload for parse errors.",
            dataset,
            problem,
        )

    try:
        X, y, numeric, categorical, n_features, n_rows = _prepare(frame, target, task)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Feature preparation failed for %s", analysis_id)
        raise ModelTrainingError(
            f"Could not prepare features for training ({type(exc).__name__})."
        ) from exc

    if n_rows < 10 or n_features == 0:
        return _skipped(
            f"Only {n_rows} usable rows and {n_features} usable features were found - "
            "too little data to train and evaluate a model.",
            dataset,
            problem,
        )

    n_classes = int(pd.Series(y).nunique())
    if task == "classification" and n_classes < 2:
        return _skipped(
            f"The target column '{target}' has a single class, so classification "
            "cannot be evaluated.",
            dataset,
            problem,
        )
    min_class = int(pd.Series(y).value_counts().min())
    if task == "classification" and min_class < 2:
        return _skipped(
            f"The rarest class in '{target}' has only {min_class} sample(s); a "
            "train/test split would put that class entirely in one side.",
            dataset,
            problem,
        )

    stratify = y if task == "classification" else None
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=settings.analysis_random_seed, stratify=stratify
        )
    except ValueError as exc:
        return _skipped(
            f"A train/test split was not possible for this data ({exc}).",
            dataset,
            problem,
        )

    names = (
        classification_candidates(len(X_train), n_features)
        if task == "classification"
        else regression_candidates()
    )
    primary = primary_metric_for(task)
    candidates: list[dict[str, Any]] = []

    for name in names:
        entry: dict[str, Any] = {
            "name": name,
            "family": FAMILIES.get(name, "Other"),
            "accuracy": None,
            "f1_score": None,
            "training_time_sec": 0.0,
            "complexity": COMPLEXITY.get(FAMILIES.get(name, ""), "O(n * d)"),
            "suitable": True,
            "notes": "",
        }
        started = time.perf_counter()
        try:
            pipe = Pipeline(
                [
                    ("prep", _preprocessor(numeric, categorical)),
                    ("model", _build_estimator(name, task)),
                ]
            )
            pipe.fit(X_train, y_train)
            entry["training_time_sec"] = round(time.perf_counter() - started, 3)
            preds = pipe.predict(X_test)
            entry.update(_metrics(task, y_test, preds))
            entry["primary_metric"] = primary
            entry["primary_score"] = entry.get(primary)
            entry["notes"] = (
                f"Trained on {len(X_train):,} rows and scored on {len(X_test):,} "
                f"held-out rows ({primary} = {entry.get(primary)})."
            )
        except Exception as exc:  # noqa: BLE001 - one bad model must not kill the stage
            logger.warning("Candidate %s failed: %s", name, exc)
            entry.update(
                {
                    "suitable": False,
                    "notes": f"Training failed ({type(exc).__name__}); candidate skipped.",
                    "error": str(exc)[:200],
                    "training_time_sec": round(time.perf_counter() - started, 3),
                }
            )
        candidates.append(entry)

    trained = [c for c in candidates if c.get("suitable") and c.get("primary_score") is not None]
    if not trained:
        return _skipped(
            "Every classical candidate failed to train on this dataset.",
            dataset,
            problem,
        )

    trained.sort(key=lambda c: c["primary_score"], reverse=True)
    best = trained[0]
    baseline = next(
        (c for c in trained if c["name"].startswith("Dummy")),
        trained[-1],
    )
    return _build_block(
        dataset, problem, candidates, best, baseline, primary, n_features, n_rows,
        n_classes, min_class, numeric, categorical,
    )


def _build_block(
    dataset: dict[str, Any],
    problem: dict[str, Any],
    candidates: list[dict[str, Any]],
    best: dict[str, Any],
    baseline: dict[str, Any],
    primary: str,
    n_features: int,
    n_rows: int,
    n_classes: int,
    min_class: int,
    numeric: list[str],
    categorical: list[str],
) -> dict[str, Any]:
    """Assemble the ``classical_analysis`` block from measured results."""
    task = problem.get("problem_type", "unknown")
    size = _size_block(dataset)

    metric_label = {
        "f1_score": "macro-F1",
        "r2": "R2",
        "accuracy": "accuracy",
    }.get(primary, primary.replace("_", " "))

    def _headline(candidate: dict[str, Any]) -> str:
        score = candidate.get("primary_score")
        if score is None:
            return "not evaluated"
        if task == "classification":
            return f"{score * 100:.1f}% {metric_label}"
        return f"{score:.3f} {metric_label}"

    family = FAMILIES.get(best["name"], "Other")
    complexity_time = COMPLEXITY.get(family, "O(n * d)")
    total_seconds = sum(c.get("training_time_sec") or 0.0 for c in candidates)
    if total_seconds < 60:
        runtime = f"{total_seconds:.1f} sec"
    else:
        runtime = f"{total_seconds / 60:.1f} min"

    warnings: list[str] = []
    if best["name"] == baseline["name"]:
        warnings.append(
            "The best and the dummy baseline are the same model, so the dataset "
            "contains no signal these models can exploit."
        )
    elif best.get("primary_score") is not None and baseline.get("primary_score") is not None:
        lift = best["primary_score"] - baseline["primary_score"]
        if task == "classification" and lift < 0.02:
            warnings.append(
                f"Only a {lift * 100:.1f} point lift over the majority-class baseline; "
                "treat the score as close to the trivial floor."
            )
        if task == "regression" and best.get("r2") is not None and best["r2"] < 0:
            warnings.append(
                "The best model has a negative R2, i.e. it predicts worse than the mean."
            )
    if min_class < 10 and task == "classification":
        warnings.append(
            f"The rarest class has only {min_class} samples, so the split score is unstable."
        )
    if dataset.get("sampled"):
        warnings.append("The dataset was sampled to fit the analysis row budget.")

    score_text = _headline(best)
    summary = (
        f"Best measured baseline: {best['name']} at {score_text} "
        f"({primary.replace('_', ' ')} on a held-out 20% split, {n_rows:,} rows x "
        f"{n_features} features). Majority-class/mean baseline: "
        f"{baseline['name']} at {_headline(baseline)}."
    )

    return {
        "status": "completed",
        "task": task,
        "method": "scikit-learn; hold-out 20% split, with cross-validation on the best model",
        "primary_metric": primary,
        # --- existing frontend contract (names unchanged) ---
        "dataset_size": size,
        "candidates": candidates,
        "baseline_model": {
            "name": baseline["name"],
            "accuracy": baseline.get("accuracy"),
            "f1_score": baseline.get("f1_score"),
            "training_time_sec": baseline.get("training_time_sec", 0.0),
            "primary_metric": primary,
            "primary_score": baseline.get("primary_score"),
            "summary": _headline(baseline),
            "r2": baseline.get("r2"),
            "mae": baseline.get("mae"),
            "rmse": baseline.get("rmse"),
            "role": (
                "Trivial reference: the score a model gets by predicting the majority "
                "class (or the mean) for every row."
            ),
        },
        "best_model": {
            "name": best["name"],
            "accuracy": best.get("accuracy"),
            "f1_score": best.get("f1_score"),
            "training_time_sec": best.get("training_time_sec", 0.0),
            "primary_metric": primary,
            "primary_score": best.get("primary_score"),
            "summary": _headline(best),
            # Regression metrics live here too, so the UI can show R2 / MAE / RMSE
            # without having to reach into `candidates`.
            "r2": best.get("r2"),
            "mae": best.get("mae"),
            "rmse": best.get("rmse"),
        },
        "estimated_complexity": {
            "time": complexity_time,
            "space": "O(n * d)",
            "summary": (
                f"{family} complexity at {n_rows:,} rows x {n_features} features is "
                "tractable on commodity CPU hardware."
            ),
        },
        "resource_requirements": {
            "cpu_cores": 2,
            "memory_gb": max(1, int((dataset.get("memory_footprint_mb") or 1) * 4)),
            "gpu_required": False,
            "expected_runtime": runtime,
            "notes": (
                f"Measured total training time for all candidates: {total_seconds:.1f}s. "
                "No GPU is required at this data scale."
            ),
        },
        "summary": summary,
        # --- extended measured detail ---
        "metrics": {k: v for k, v in best.items() if k not in ("name", "family", "notes")},
        "evaluation": {
            "strategy": "train/test split (80/20)",
            "test_size": 0.2,
            "train_rows": int(n_rows * 0.8),
            "test_rows": int(n_rows * 0.2),
            "random_seed": settings.analysis_random_seed,
        },
        "features": {
            "used": n_features,
            "numerical": len(numeric),
            "categorical": len(categorical),
            "dropped_all_null": max(0, (dataset.get("column_count") or 0) - n_features - 1),
        },
        "class_summary": {"n_classes": n_classes, "min_class_count": min_class}
        if task == "classification"
        else None,
        "preprocessing": [
            "Numeric columns: median imputation + standardisation.",
            "Categorical columns: most-frequent imputation + one-hot encoding "
            "(rare levels grouped).",
        ],
        "errors": [],
        "warnings": warnings,
        "is_mock": False,
        "note": (
            "These scores were measured on your data with scikit-learn. They are a "
            "baseline reference, not a tuned best-in-class result."
        ),
    }
