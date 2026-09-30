"""Typed errors for the analysis engine.

Every failure mode the engine can hit is expressed as an :class:`AnalysisError`
subclass carrying the HTTP status and a message that is safe (and useful) to show
a user. Services raise these; ``routes/`` and the global handler in ``main.py``
turn them into JSON. That keeps "return a useful error instead of crashing" a
structural property of the codebase rather than a convention.
"""

from __future__ import annotations

from typing import Any

# Numeric status codes are used instead of starlette's named constants because
# several of them were renamed in newer Starlette releases, and a deprecation
# warning is not worth emitting from an import.
HTTP_400 = 400
HTTP_413 = 413
HTTP_415 = 415
HTTP_422 = 422
HTTP_500 = 500
HTTP_503 = 503


class AnalysisError(Exception):
    """Base class for every error the analysis pipeline raises on purpose."""

    status_code: int = HTTP_400
    error_code: str = "analysis_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON body for this error."""
        payload: dict[str, Any] = {
            "detail": self.message,
            "error_code": self.error_code,
        }
        if self.details:
            payload["details"] = self.details
        return payload


class UnsupportedFileTypeError(AnalysisError):
    """The upload is not a format the engine can parse."""

    status_code = HTTP_415
    error_code = "unsupported_file_type"


class ParseError(AnalysisError):
    """The file could not be parsed as the format it claims to be."""

    status_code = HTTP_422
    error_code = "parse_error"


class EmptyDatasetError(AnalysisError):
    """The file parsed, but contains no usable rows."""

    status_code = HTTP_422
    error_code = "empty_dataset"


class DatasetTooLargeError(AnalysisError):
    """The file exceeds the engine's hard row budget and cannot be sampled down."""

    status_code = HTTP_413
    error_code = "dataset_too_large"


class MissingTargetError(AnalysisError):
    """A supervised task was requested but no target column could be resolved."""

    status_code = HTTP_422
    error_code = "missing_target"


class NonNumericDataError(AnalysisError):
    """Numeric data was required but the relevant columns are categorical."""

    status_code = HTTP_422
    error_code = "non_numeric_data"


class InsufficientSamplesError(AnalysisError):
    """Too few rows / classes to train and evaluate a model."""

    status_code = HTTP_422
    error_code = "insufficient_samples"


class ModelTrainingError(AnalysisError):
    """An estimator failed to fit."""

    status_code = HTTP_500
    error_code = "model_training_failed"


class InvalidProblemDescriptionError(AnalysisError):
    """The problem statement is not usable text."""

    status_code = HTTP_422
    error_code = "invalid_problem_description"


class QuantumLibraryUnavailableError(AnalysisError):
    """A quantum framework was required but is not installed."""

    status_code = HTTP_503
    error_code = "quantum_library_unavailable"
