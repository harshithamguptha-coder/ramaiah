"""Mock report builder: structured sections + a Markdown rendering."""

from __future__ import annotations

from typing import Any

from utils.ids import utc_now_iso


def _table(rows: list[list[str]], header: list[str]) -> dict[str, Any]:
    return {"type": "table", "header": header, "rows": rows}


def _attr_rows(pairs: list[tuple[str, Any]]) -> list[list[str]]:
    return [[label, str(value) if value is not None else "—"] for label, value in pairs]


def build_report_block(payload: dict[str, Any]) -> dict[str, Any]:
    """Assemble the nine report sections from the already-built payload blocks."""
    dataset = payload.get("dataset", {})
    problem = payload.get("problem", {})
    classical = payload.get("classical_analysis", {})
    quantum = payload.get("quantum_analysis", {})
    comparison = payload.get("comparison", {})
    recommendation = payload.get("recommendation", {})

    sections: list[dict[str, Any]] = [
        {
            "key": "problem_overview",
            "title": "Problem Overview",
            "blocks": [
                {"type": "text", "body": problem.get("description", "—")},
                _table(
                    _attr_rows([
                        ("Task type", problem.get("task_type")),
                        ("Learning paradigm", problem.get("learning_paradigm")),
                        ("Inference confidence", f"{problem.get('task_type_confidence', 0) * 100:.0f}%"),
                        ("Modality", ", ".join(problem.get("detected_modalities", []))),
                    ]),
                    ["Attribute", "Value"],
                ),
            ],
        },
        {
            "key": "dataset_summary",
            "title": "Dataset Summary",
            "blocks": [
                _table(
                    _attr_rows([
                        ("File", dataset.get("file_name")),
                        ("Size", dataset.get("file_size_display")),
                        ("Rows", f"{dataset['rows']:,}" if dataset.get("rows") else "Not parsed"),
                        ("Columns", dataset.get("column_count") or "Not parsed"),
                        ("Numerical features", dataset.get("numerical_features")),
                        ("Categorical features", dataset.get("categorical_features")),
                        ("Missing values", dataset.get("missing_values")),
                        ("Target column", dataset.get("target_column") or "Not detected"),
                    ]),
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
                        [c["name"], f"{c['accuracy'] * 100:.1f}%", f"{c['training_time_sec']} sec"]
                        for c in classical.get("candidates", [])
                    ],
                    ["Candidate", "Accuracy", "Training time"],
                ),
                {"type": "text", "body": classical.get("summary", "")},
            ],
        },

        {
            "key": "quantum_analysis",
            "title": "Quantum AI Analysis",
            "blocks": [
                _table(
                    _attr_rows([
                        ("Suitability score", f"{quantum.get('suitability_score')}/100"),
                        ("Label", quantum.get("suitability_label")),
                        ("Primary algorithm", quantum.get("primary_algorithm")),
                        ("Qubits required", quantum.get("qubits_required")),
                        ("Circuit depth", quantum.get("circuit_complexity", {}).get("depth")),
                        ("Feasibility", quantum.get("feasibility")),
                    ]),
                    ["Attribute", "Value"],
                ),
            ],
        },
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
                {"type": "callout", "body": recommendation.get("headline", "—")},
                {"type": "text", "body": recommendation.get("summary", "")},
            ],
        },
        {
            "key": "reasoning",
            "title": "Reasoning",
            "blocks": [
                {
                    "type": "list",
                    "items": [r["detail"] for r in recommendation.get("reasons", [])],
                }
            ],
        },
        {
            "key": "limitations",
            "title": "Limitations",
            "blocks": [
                {"type": "list", "items": recommendation.get("limitations", [])},
                {"type": "callout", "tone": "warning", "body": recommendation.get("disclaimer", "")},
            ],
        },
        {
            "key": "next_steps",
            "title": "Suggested Next Steps",
            "blocks": [
                {
                    "type": "list",
                    "ordered": True,
                    "items": recommendation.get("suggested_next_steps", []),
                }
            ],
        },
    ]

    return {
        "analysis_id": payload.get("analysis_id"),
        "generated_at": utc_now_iso(),
        "title": "Q-Compass Analysis Report",
        "sections": sections,
        "markdown": _to_markdown("Q-Compass Analysis Report", sections),
        "is_mock": True,
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
