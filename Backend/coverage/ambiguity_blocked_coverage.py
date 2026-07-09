from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

AMBIGUOUS_STATUSES = {
    "Ambiguous / not yet plannable",
    "ambiguous",
    "blocked_by_ambiguity",
    "ambiguity_blocked",
}

BLOCKED_COVERAGE_VALUES = {
    "blocked",
    "Blocked",
}


def load_json(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_spec_requirements(spec_data: dict[str, Any]) -> list[dict[str, Any]]:
    requirements = spec_data.get("requirements", [])

    if not isinstance(requirements, list):
        raise ValueError("Spec JSON must contain a top-level 'requirements' list.")

    return requirements


def extract_labelled_requirements(
    coverage_data: dict[str, Any],
) -> list[dict[str, Any]]:
    labelled_requirements = coverage_data.get("labelled_requirements", [])

    if not isinstance(labelled_requirements, list):
        raise ValueError(
            "Coverage JSON must contain a top-level 'labelled_requirements' list."
        )

    return labelled_requirements


def get_requirement_key(requirement: dict[str, Any]) -> str | None:
    requirement_id = requirement.get("id") or requirement.get("requirement_id")

    if requirement_id is None:
        return None

    return str(requirement_id)


def has_ambiguity_signal(labelled_requirement: dict[str, Any]) -> bool:
    linked_edge_cases = labelled_requirement.get("linked_edge_cases", [])
    linked_weak_word_flags = labelled_requirement.get("linked_weak_word_flags", [])

    return bool(linked_edge_cases) or bool(linked_weak_word_flags)


def has_blocked_test(labelled_requirement: dict[str, Any]) -> bool:
    original_vplan_coverage_values = labelled_requirement.get(
        "original_vplan_coverage_values",
        [],
    )

    return any(
        coverage_value in BLOCKED_COVERAGE_VALUES
        for coverage_value in original_vplan_coverage_values
    )


def is_ambiguity_blocked(labelled_requirement: dict[str, Any]) -> bool:
    verified_status = labelled_requirement.get("verified_coverage_status")

    if verified_status in AMBIGUOUS_STATUSES:
        return True

    return has_blocked_test(labelled_requirement) and has_ambiguity_signal(
        labelled_requirement
    )


def calculate_ambiguity_blocked_coverage(
    spec_requirements: list[dict[str, Any]],
    labelled_requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Ambiguity-blocked coverage =
        number of spec items blocked by ambiguity
        / total number of spec items
        * 100
    """

    total_spec_items = len(spec_requirements)

    ambiguity_blocked_by_requirement_id = {}

    for labelled_requirement in labelled_requirements:
        requirement_id = get_requirement_key(labelled_requirement)

        if requirement_id is None:
            continue

        if is_ambiguity_blocked(labelled_requirement):
            ambiguity_blocked_by_requirement_id[requirement_id] = labelled_requirement

    ambiguity_blocked_requirements = []
    not_ambiguity_blocked_requirements = []

    for index, requirement in enumerate(spec_requirements):
        requirement_id = get_requirement_key(requirement)

        requirement_summary = {
            "requirement_index": index,
            "requirement_id": requirement_id,
            "source_section": requirement.get("source_section"),
            "text": requirement.get("text"),
        }

        if requirement_id in ambiguity_blocked_by_requirement_id:
            labelled_match = ambiguity_blocked_by_requirement_id[requirement_id]

            requirement_summary["verified_coverage_status"] = labelled_match.get(
                "verified_coverage_status"
            )
            requirement_summary["coverage_verification_reason"] = labelled_match.get(
                "coverage_verification_reason"
            )
            requirement_summary["linked_tests"] = labelled_match.get("linked_tests", [])
            requirement_summary["linked_edge_cases"] = labelled_match.get(
                "linked_edge_cases",
                [],
            )
            requirement_summary["linked_weak_word_flags"] = labelled_match.get(
                "linked_weak_word_flags",
                [],
            )

            ambiguity_blocked_requirements.append(requirement_summary)
        else:
            not_ambiguity_blocked_requirements.append(requirement_summary)

    ambiguity_blocked_count = len(ambiguity_blocked_requirements)

    coverage_percentage = (
        round((ambiguity_blocked_count / total_spec_items) * 100, 2)
        if total_spec_items > 0
        else 0.0
    )

    return {
        "metric_name": "Ambiguity-Blocked Coverage",
        "definition": "Percentage of spec items blocked by ambiguity.",
        "formula": "(spec_items_blocked_by_ambiguity / total_spec_items) * 100",
        "total_spec_items": total_spec_items,
        "spec_items_blocked_by_ambiguity": ambiguity_blocked_count,
        "spec_items_not_blocked_by_ambiguity": len(not_ambiguity_blocked_requirements),
        "ambiguity_blocked_coverage": coverage_percentage,
        "ambiguity_blocked_requirements": ambiguity_blocked_requirements,
    }


def run_ambiguity_blocked_coverage(
    spec_file: str | Path,
    coverage_file: str | Path,
) -> dict[str, Any]:
    spec_data = load_json(spec_file)
    coverage_data = load_json(coverage_file)

    spec_requirements = extract_spec_requirements(spec_data)
    labelled_requirements = extract_labelled_requirements(coverage_data)

    return calculate_ambiguity_blocked_coverage(
        spec_requirements=spec_requirements,
        labelled_requirements=labelled_requirements,
    )


def print_ambiguity_blocked_summary(result: dict[str, Any]) -> None:
    print("\nAmbiguity-Blocked Coverage")
    print("--------------------------")
    print(f"Total spec items:                    {result['total_spec_items']}")
    print(
        "Spec items blocked by ambiguity:     "
        f"{result['spec_items_blocked_by_ambiguity']}"
    )
    print(
        "Spec items not ambiguity-blocked:    "
        f"{result['spec_items_not_blocked_by_ambiguity']}"
    )
    print(
        f"Coverage:                            {result['ambiguity_blocked_coverage']}%"
    )

    if result["ambiguity_blocked_requirements"]:
        print("\nAmbiguity-blocked requirement IDs:")
        for requirement in result["ambiguity_blocked_requirements"]:
            print(f"  - {requirement['requirement_id']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate deterministic ambiguity-blocked coverage."
    )

    parser.add_argument(
        "--spec-file",
        required=True,
        help="Path to the extracted spec JSON file.",
    )

    parser.add_argument(
        "--coverage-file",
        required=True,
        help="Path to the labelled coverage JSON file.",
    )

    args = parser.parse_args()

    result = run_ambiguity_blocked_coverage(
        spec_file=args.spec_file,
        coverage_file=args.coverage_file,
    )

    print_ambiguity_blocked_summary(result)
