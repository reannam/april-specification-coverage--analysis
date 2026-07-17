from pathlib import Path
from datetime import datetime
import json

from Backend.config import UNCOVERED_TESTS_DIR, WEAK_LANGUAGE_TERMS_FILE
from Backend.text_config import load_grouped_text_config, require_groups

TERM_GROUPS, _ = load_grouped_text_config(WEAK_LANGUAGE_TERMS_FILE)
require_groups(
    TERM_GROUPS,
    {
        "clarification_implementation_terms",
        "clarification_observability_terms",
        "clarification_missing_detail_terms",
    },
    source=WEAK_LANGUAGE_TERMS_FILE,
)


def load_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def build_edge_case_lookup(edge_case_data: dict) -> dict[str, list[dict]]:
    lookup = {}

    for edge_case in edge_case_data.get("edge_cases", []):
        requirement_id = edge_case.get("requirement_id")

        if not requirement_id:
            continue

        lookup.setdefault(requirement_id, []).append(edge_case)

    return lookup


def infer_required_clarification(row: dict, related_edge_cases: list[dict]) -> str:
    """Map known constraint language to the next clarification an engineer needs."""

    constraints = row.get("test_constraints", "").lower()

    if any(
        term in constraints
        for term in TERM_GROUPS["clarification_implementation_terms"]
    ):
        return "Confirm implementation-specific configuration before verification."

    if any(
        term in constraints for term in TERM_GROUPS["clarification_observability_terms"]
    ):
        return "Define observable pass/fail criteria for this requirement."

    if any(
        term in constraints
        for term in TERM_GROUPS["clarification_missing_detail_terms"]
    ):
        return (
            "Provide the missing signal, timing, configuration, or behavioural detail."
        )

    if related_edge_cases:
        return "Clarify the edge-case behaviour before treating this requirement as fully testable."

    return "Review requirement wording and provide enough detail for verification."


def export_uncovered_test_report(
    vplan_file: str | Path,
    edge_case_file: str | Path,
) -> Path:
    vplan_data = load_json(vplan_file)
    edge_case_data = load_json(edge_case_file)

    edge_case_lookup = build_edge_case_lookup(edge_case_data)

    uncovered_tests = []
    partially_covered_tests = []

    for row in vplan_data.get("feature_list", []):
        coverage = row.get("coverage")

        if coverage not in {"uncovered", "partially_covered"}:
            continue

        requirement_id = row.get("requirement_id")
        related_edge_cases = edge_case_lookup.get(requirement_id, [])

        record = {
            "test_id": row.get("test_id"),
            "requirement_id": requirement_id,
            "coverage": coverage,
            "test_description": row.get("test_description") or "",
            "reason": row.get("test_constraints"),
            "required_clarification": infer_required_clarification(
                row, related_edge_cases
            ),
            "related_edge_cases": [
                {
                    "edge_case_id": edge_case.get("edge_case_id"),
                    "edge_case_type": edge_case.get("edge_case_type"),
                    "edge_case_description": edge_case.get("edge_case_description"),
                }
                for edge_case in related_edge_cases
            ],
        }

        if coverage == "uncovered":
            uncovered_tests.append(record)
        else:
            partially_covered_tests.append(record)

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

    report = {
        "metadata": {
            "vplan_file": str(vplan_file),
            "edge_case_file": str(edge_case_file),
            "date_created": now.strftime("%B %d %Y"),
            "time_created": now.strftime("%I:%M%p").lower(),
            "number_of_uncovered_tests": len(uncovered_tests),
            "number_of_partially_covered_tests": len(partially_covered_tests),
        },
        "uncovered_tests": uncovered_tests,
        "partially_covered_tests": partially_covered_tests,
    }

    output_file = UNCOVERED_TESTS_DIR / f"uncovered_test_report_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    return output_file
