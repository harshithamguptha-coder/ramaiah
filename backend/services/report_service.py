"""Stage 7 — report generation.

Builds the nine structured report sections from an already-complete payload and
renders the same content as a downloadable Markdown document. It is a pure
formatter: every number it prints came from an upstream stage.
"""

from __future__ import annotations

from typing import Any

from utils.ids import utc_now_iso
from utils.logging_config import get_logger

logger = get_logger(__name__)


def _table(rows: list[list[str]], header: list[str]) -> dict[str, Any]:
    return {"type": "table", "header": header, "rows": rows}


def _attr_rows(pairs: list[tuple[str, Any]]) -> list[list[str]]:
    return [[label, "-" if value is None else str(value)] for label, value in pairs]


def _pct(value: Any) -> str:
    return "-" if value is None else f"{float(value) * 100:.1f}%"


def _metric_text(candidate: dict[str, Any]) -> str:
    """Format one candidate row for the report, per task type."""
    if candidate.get("accuracy") is not None:
        return f"{_pct(candidate.get('accuracy'))} acc / {_pct(candidate.get('f1_score'))} F1"
    if candidate.get("r2") is not None:
        return f"R2 {candidate.get('r2')}"
    return "not evaluated"


def build_report_block(payload: dict[str, Any]) -> dict[str, Any]:
    """Assemble the report sections from the completed payload."""
    dataset = payload.get("dataset", {})
    problem = payload.get("problem", {})
    classical = payload.get("classical_analysis", {})
    quantum = payload.get("quantum_analysis", {})
    comparison = payload.get("comparison", {})
    recommendation = payload.get("recommendation", {})

    characteristics = problem.get("characteristics", {})
    sections: list[dict[str, Any]] = [
        {
            "key": "problem_overview",
            "title": "Problem Overview",
            "blocks": [
                {"type": "text", "body": problem.get("description", "-")},
                _table(
                    _attr_rows(
                        [
                            ("Task type", problem.get("task_type")),
                            ("Problem type", problem.get("problem_type")),
                            ("Learning paradigm", problem.get("learning_paradigm")),
                            ("Inference confidence", f"{problem.get('task_type_confidence', 0) * 100:.0f}%"),
                            ("Target column", problem.get("target_column") or "not detected"),
                            ("Features", characteristics.get("features")),
                            ("Search space (log2)", characteristics.get("estimated_search_space_log2")),
                        ]
                    ),
                    ["Attribute", "Value"],
                ),
                {"type": "list", "items": (problem.get("detection") or {}).get("signals", [])},
            ],
        },
        {
            "key": "dataset_summary",
            "title": "Dataset Summary",
            "blocks": [
                _table(
                    _attr_rows(
                        [
                            ("File", dataset.get("file_name")),
                            ("Size", dataset.get("file_size_display")),
                            ("Rows", dataset.get("rows")),
                            ("Columns", dataset.get("column_count")),
                            ("Numerical features", dataset.get("numerical_features")),
                            ("Categorical features", dataset.get("categorical_features")),
                            ("Missing values", dataset.get("missing_values")),
                            ("Missing percent", dataset.get("missing_percent")),
                            ("Duplicate rows", dataset.get("duplicate_rows")),
                            ("Class distribution", dataset.get("class_distribution")),
                            ("Target column", dataset.get("target_column") or "not detected"),
                            ("Target source", dataset.get("target_source") or "n/a"),
                            ("Classes", dataset.get("class_count")),
                            ("Profile method", dataset.get("profile_method")),
                        ]
                    ),
                    ["Attribute", "Value"],
                ),
            ],
        },
        {
            "key": "classical_analysis",
            "title": "Classical AI Analysis",
            "blocks": [
                _table(
                    [
                        [
                            c.get("name", "-"),
                            _metric_text(c),
                            f"{c.get('training_time_sec', 0)} s",
                        ]
                        for c in classical.get("candidates", [])
                    ],
                    ["Candidate", "Measured score", "Training time"],
                ),
                {"type": "text", "body": classical.get("summary", "")},
                {
                    "type": "callout",
                    "tone": "info",
                    "body": (
                        f"Baseline reference ({classical.get('baseline_model', {}) or {}}): "
                        + str((classical.get("baseline_model") or {}).get("role", ""))
                    ),
                },
            ],
        },
        {
            "key": "quantum_analysis",
            "title": "Quantum AI Analysis",
            "blocks": [
                _table(
                    _attr_rows(
                        [
                            ("Suitability score", f"{quantum.get('suitability_score')}/100"),
                            ("Label", quantum.get("suitability_label")),
                            ("Primary method", quantum.get("primary_algorithm")),
                            ("Qubits required", quantum.get("qubits_required")),
                            ("Hardware feasibility", quantum.get("feasibility")),
                            ("Execution mode", (quantum.get("execution") or {}).get("mode")),
                            ("Hardware executed", (quantum.get("execution") or {}).get("hardware_executed")),
                        ]
                    ),
                    ["Attribute", "Value"],
                ),
                {
                    "type": "table",
                    "header": ["Factor", "Weight", "Normalised", "Contribution"],
                    "rows": [
                        [
                            f.get("label", f.get("key")),
                            f.get("weight"),
                            f.get("normalised"),
                            f.get("contribution"),
                        ]
                        for f in (quantum.get("scoring") or {}).get("factors", [])
                    ],
                },
                {"type": "list", "items": quantum.get("reasoning", [])},
            ],
        },
    ]

    sections += [
        {
            "key": "comparison",
            "title": "Classical vs Quantum Comparison",
            "blocks": [
                _table(
                    [
                        [
                            c["criterion"],
                            str(c["classical"]["score"]),
                            str(c["quantum"]["score"]),
                            str(c["hybrid"]["score"]),
                        ]
                        for c in comparison.get("criteria", [])
                    ],
                    ["Criterion", "Classical", "Quantum", "Hybrid"],
                ),
                {"type": "text", "body": comparison.get("summary", "")},
            ],
        },
        {
            "key": "recommended_approach",
            "title": "Recommended Approach",
            "blocks": [
                {"type": "callout", "body": recommendation.get("headline", "-")},
                {"type": "text", "body": recommendation.get("summary", "")},
                _table(
                    _attr_rows(
                        [
                            ("Approach", recommendation.get("recommended_approach")),
                            ("Decision gate", recommendation.get("gate")),
                            ("Confidence", f"{recommendation.get('confidence', 0) * 100:.0f}%"),
                            ("Input confidence", recommendation.get("input_confidence")),
                            ("Decision basis", recommendation.get("decision_basis")),
                        ]
                    ),
                    ["Attribute", "Value"],
                ),
            ],
        },
        {
            "key": "reasoning",
            "title": "Reasoning",
            "blocks": [
                {
                    "type": "list",
                    "items": [f'{r["title"]}: {r["detail"]}' for r in recommendation.get("reasons", [])],
                },
                {"type": "text", "body": "Alternatives considered: " + ", ".join(
                    f"{a['approach']} ({a['why_not']})"
                    for a in recommendation.get("alternatives_considered", [])
                )},
            ],
        },
        {
            "key": "limitations",
            "title": "Limitations",
            "blocks": [
                {"type": "list", "items": recommendation.get("limitations", [])},
                {"type": "callout", "tone": "warning", "body": recommendation.get("disclaimer", "")},
                {
                    "type": "callout",
                    "tone": "warning",
                    "body": quantum.get("score_interpretation", ""),
                },
            ],
        },
        {
            "key": "next_steps",
            "title": "Suggested Next Steps",
            "blocks": [
                {"type": "list", "ordered": True, "items": recommendation.get("suggested_next_steps", [])}
            ],
        },
    ]

    return {
        "analysis_id": payload.get("analysis_id"),
        "generated_at": utc_now_iso(),
        "title": "Q-Compass Analysis Report",
        "sections": sections,
        "markdown": _to_markdown("Q-Compass Analysis Report", sections),
        "is_mock": False,
    }


def _to_markdown(title: str, sections: list[dict[str, Any]]) -> str:
    """Render the structured sections as a Markdown document."""
    lines = [f"# {title}", ""]
    for section in sections:
        lines += [f"## {section['title']}", ""]
        for block in section["blocks"]:
            kind = block["type"]
            if kind == "text":
                lines += [block["body"], ""]
            elif kind == "callout":
                lines += [f"> {block['body']}", ""]
            elif kind == "list":
                for index, item in enumerate(block["items"], start=1):
                    prefix = f"{index}." if block.get("ordered") else "-"
                    lines.append(f"{prefix} {item}")
                lines.append("")
            elif kind == "table":
                lines.append("| " + " | ".join(block["header"]) + " |")
                lines.append("| " + " | ".join("---" for _ in block["header"]) + " |")
                for row in block["rows"]:
                    lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
                lines.append("")
    return "\n".join(lines)


def run(payload: dict[str, Any]) -> dict[str, Any]:
    """Produce the report block from a complete analysis payload."""
    return build_report_block(payload)
