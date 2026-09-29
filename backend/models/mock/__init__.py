"""Centralised mock data source for the Q-Compass prototype.

Every fabricated value in the system originates in this package. Nothing here
performs real analysis — each builder is a deterministic placeholder that will
be replaced by a real engine later, without changing the payload contract.

Payload contract (stable)::

    {
      "analysis_id": str, "status": str, "data_source": "mock",
      "pipeline": [...], "dataset": {...}, "problem": {...},
      "classical_analysis": {...}, "quantum_analysis": {...},
      "comparison": {...}, "recommendation": {...}, "report": {...},
    }
"""

from .classical import CLASSICAL_CATALOGUE, build_classical_block
from .common import APPROACH_LABELS, MOCK_NOTE, pick_task_type, rnd, rng_for
from .comparison import APPROACH_KEYS, build_comparison_block
from .dataset import build_dataset_block, build_problem_block
from .pipeline import PIPELINE_STAGES, build_pipeline
from .quantum import QUANTUM_CATALOGUE, build_quantum_block
from .recommendation import build_recommendation_block
from .report import build_report_block

__all__ = [
    "APPROACH_KEYS",
    "APPROACH_LABELS",
    "CLASSICAL_CATALOGUE",
    "MOCK_NOTE",
    "PIPELINE_STAGES",
    "QUANTUM_CATALOGUE",
    "build_classical_block",
    "build_comparison_block",
    "build_dataset_block",
    "build_pipeline",
    "build_problem_block",
    "build_quantum_block",
    "build_recommendation_block",
    "build_report_block",
    "pick_task_type",
    "rnd",
    "rng_for",
]
