from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FULLY_COVERED_STATUSES = {
    "covered",
    "Covered",
    "fully_covered",
    "Fully covered",
    "Fully Covered",
}

PARTIALLY_COVERED_STATUSES = {
    "partially_covered",
    "Partially covered",
    "Partially Covered",
}

NOT_COVERED_STATUSES = {
    "uncovered",
    "Uncovered",
    "not_covered",
    "Not covered",
    "Not Covered",
    "blocked",
    "Blocked",
    "ambiguous",
    "Ambiguous",
    "ambiguous / not yet plannable",
    "Ambiguous / not yet plannable",
}


def load_json(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_labelled_requirements(
    coverage_data: dict[str, Any],
) -> list[dict[str, Any]]:
    labelled_requirements = coverage_data.get("labelled_requirements", [])

    if not isinstance(labelled_requirements, list):
        raise ValueError(
            "Coverage JSON must contain a top-level 'labelled_requirements' list."
        )

    return labelled_requirements


def status_to_weight(status: str | None) -> float:
    if status in FULLY_COVERED_STATUSES:
        return 1.0

    if status in PARTIALLY_COVERED_STATUSES:
        return 0.5

    if status in NOT_COVERED_STATUSES:
        return 0.0

    return 0.0


def calculate_full_vs_partial_coverage(
    labelled_requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Weighted Coverage =
        sum(c_i) / N * 100

    where:
        c_i ∈ {1, 0.5, 0}

    Fully covered = 1.0
    Partially covered = 0.5
    Not covered = 0.0
    """

    total_requirements = len(labelled_requirements)

    fully_covered = []
    partially_covered = []
    not_covered = []

    weighted_items = []

    for index, requirement in enumerate(labelled_requirements):
        status = requirement.get("verified_coverage_status")
        weight = status_to_weight(status)

        item = {
            "requirement_index": index,
            "requirement_id": requirement.get("id")
            or requirement.get("requirement_id"),
            "source_section": requirement.get("source_section"),
            "verified_coverage_status": status,
            "coverage_weight": weight,
            "text": requirement.get("text"),
            "linked_tests": requirement.get("linked_tests", []),
            "coverage_verification_reason": requirement.get(
                "coverage_verification_reason"
            ),
        }

        weighted_items.append(item)

        if weight == 1.0:
            fully_covered.append(item)
        elif weight == 0.5:
            partially_covered.append(item)
        else:
            not_covered.append(item)

    weighted_score = sum(item["coverage_weight"] for item in weighted_items)

    weighted_coverage = (
        round((weighted_score / total_requirements) * 100, 2)
        if total_requirements > 0
        else 0.0
    )

    return {
        "metric_name": "Full vs Partial Coverage",
        "definition": (
            "Weighted percentage of spec items that are fully covered, "
            "partially covered, or not covered."
        ),
        "formula": "sum(c_i) / N * 100, where c_i ∈ {1, 0.5, 0}",
        "total_requirements": total_requirements,
        "fully_covered_count": len(fully_covered),
        "partially_covered_count": len(partially_covered),
        "not_covered_count": len(not_covered),
        "weighted_score": weighted_score,
        "weighted_coverage": weighted_coverage,
        "fully_covered_requirements": fully_covered,
        "partially_covered_requirements": partially_covered,
        "not_covered_requirements": not_covered,
    }


def run_full_vs_partial_coverage(coverage_file: str | Path) -> dict[str, Any]:
    coverage_data = load_json(coverage_file)
    labelled_requirements = extract_labelled_requirements(coverage_data)

    return calculate_full_vs_partial_coverage(labelled_requirements)


def print_full_vs_partial_summary(result: dict[str, Any]) -> None:
    print("\nFull vs Partial Coverage")
    print("------------------------")
    print(f"Total requirements:       {result['total_requirements']}")
    print(f"Fully covered:            {result['fully_covered_count']}")
    print(f"Partially covered:        {result['partially_covered_count']}")
    print(f"Not covered:              {result['not_covered_count']}")
    print(f"Weighted score:           {result['weighted_score']}")
    print(f"Weighted coverage:        {result['weighted_coverage']}%")

    if result["not_covered_requirements"]:
        print("\nNot covered requirement IDs:")
        for requirement in result["not_covered_requirements"]:
            print(f"  - {requirement['requirement_id']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate deterministic full vs partial weighted coverage."
    )

    parser.add_argument(
        "--coverage-file",
        required=True,
        help="Path to the output JSON from coverage_status_verifier.py.",
    )

    args = parser.parse_args()

    result = run_full_vs_partial_coverage(args.coverage_file)

    print_full_vs_partial_summary(result)
