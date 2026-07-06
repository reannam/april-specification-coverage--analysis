from pathlib import Path
from datetime import datetime
import json

from Backend.config import BLOCKED_TESTS_DIR as BLOCKED_TEST_DIR


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
    constraints = row.get("test_constraints", "").lower()

    if "implementation-dependent" in constraints or "implementation dependent" in constraints:
        return "Confirm implementation-specific configuration before verification."

    if "not define observable" in constraints or "pass/fail" in constraints:
        return "Define observable pass/fail criteria for this requirement."

    if "not specified" in constraints or "unspecified" in constraints:
        return "Provide the missing signal, timing, configuration, or behavioural detail."

    if related_edge_cases:
        return "Clarify the edge-case behaviour before treating this requirement as fully testable."

    return "Review requirement wording and provide enough detail for verification."


def export_blocked_test_report(
    vplan_file: str | Path,
    edge_case_file: str | Path,
) -> Path:
    vplan_data = load_json(vplan_file)
    edge_case_data = load_json(edge_case_file)

    edge_case_lookup = build_edge_case_lookup(edge_case_data)

    blocked_tests = []
    partially_covered_tests = []

    for row in vplan_data.get("feature_list", []):
        coverage = row.get("coverage")

        if coverage not in {"blocked", "partially_covered"}:
            continue

        requirement_id = row.get("requirement_id")
        related_edge_cases = edge_case_lookup.get(requirement_id, [])

        record = {
            "test_id": row.get("test_id"),
            "requirement_id": requirement_id,
            "coverage": coverage,
            "test_description": row.get("test_description"),
            "reason": row.get("test_constraints"),
            "required_clarification": infer_required_clarification(row, related_edge_cases),
            "related_edge_cases": [
                {
                    "edge_case_id": edge_case.get("edge_case_id"),
                    "edge_case_type": edge_case.get("edge_case_type"),
                    "edge_case_description": edge_case.get("edge_case_description"),
                }
                for edge_case in related_edge_cases
            ],
        }

        if coverage == "blocked":
            blocked_tests.append(record)
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
            "number_of_blocked_tests": len(blocked_tests),
            "number_of_partially_covered_tests": len(partially_covered_tests),
        },
        "blocked_tests": blocked_tests,
        "partially_covered_tests": partially_covered_tests,
    }

    output_file = BLOCKED_TEST_DIR / f"blocked_test_report_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    return output_file