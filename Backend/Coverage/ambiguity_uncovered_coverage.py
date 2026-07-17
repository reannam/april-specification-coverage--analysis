from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from Backend.config import COVERAGE_TERMS_FILE
from Backend.text_config import load_grouped_text_config, require_groups

TERM_GROUPS, _ = load_grouped_text_config(COVERAGE_TERMS_FILE)
require_groups(
    TERM_GROUPS,
    {"ambiguous_statuses", "not_covered_statuses"},
    source=COVERAGE_TERMS_FILE,
)
AMBIGUOUS_STATUSES = TERM_GROUPS["ambiguous_statuses"]
UNCOVERED_COVERAGE_VALUES = TERM_GROUPS["not_covered_statuses"]


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


def has_uncovered_test(labelled_requirement: dict[str, Any]) -> bool:
    original_vplan_coverage_values = labelled_requirement.get(
        "original_vplan_coverage_values",
        [],
    )

    return any(
        str(coverage_value).strip().casefold() in UNCOVERED_COVERAGE_VALUES
        for coverage_value in original_vplan_coverage_values
    )


def is_ambiguity_uncovered(labelled_requirement: dict[str, Any]) -> bool:
    verified_status = labelled_requirement.get("verified_coverage_status")

    if str(verified_status or "").strip().casefold() in AMBIGUOUS_STATUSES:
        return True

    return has_uncovered_test(labelled_requirement) and has_ambiguity_signal(
        labelled_requirement
    )


def calculate_ambiguity_uncovered_coverage(
    spec_requirements: list[dict[str, Any]],
    labelled_requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Ambiguity-related uncovered rate =
        number of spec items uncovered because of ambiguity
        / total number of spec items
        * 100
    """

    total_spec_items = len(spec_requirements)

    ambiguity_uncovered_by_requirement_id = {}

    for labelled_requirement in labelled_requirements:
        requirement_id = get_requirement_key(labelled_requirement)

        if requirement_id is None:
            continue

        if is_ambiguity_uncovered(labelled_requirement):
            ambiguity_uncovered_by_requirement_id[requirement_id] = labelled_requirement

    ambiguity_uncovered_requirements = []
    other_requirements = []

    for requirement in spec_requirements:
        requirement_id = get_requirement_key(requirement)

        requirement_summary = {
            "requirement_id": requirement_id,
            "source_section": requirement.get("source_section"),
            "text": requirement.get("text"),
        }

        if requirement_id in ambiguity_uncovered_by_requirement_id:
            labelled_match = ambiguity_uncovered_by_requirement_id[requirement_id]

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

            ambiguity_uncovered_requirements.append(requirement_summary)
        else:
            other_requirements.append(requirement_summary)

    ambiguity_uncovered_count = len(ambiguity_uncovered_requirements)

    coverage_percentage = (
        round((ambiguity_uncovered_count / total_spec_items) * 100, 2)
        if total_spec_items > 0
        else 0.0
    )

    return {
        "metric_name": "Ambiguity-Related Uncovered Rate",
        "definition": "Percentage of specification items that are uncovered with linked ambiguity evidence.",
        "formula": "(spec_items_uncovered_due_to_ambiguity / total_spec_items) * 100",
        "total_spec_items": total_spec_items,
        "spec_items_uncovered_due_to_ambiguity": ambiguity_uncovered_count,
        "other_spec_items": len(other_requirements),
        "ambiguity_uncovered_rate": coverage_percentage,
        "ambiguity_uncovered_requirements": ambiguity_uncovered_requirements,
    }


def run_ambiguity_uncovered_coverage(
    spec_file: str | Path,
    coverage_file: str | Path,
) -> dict[str, Any]:
    spec_data = load_json(spec_file)
    coverage_data = load_json(coverage_file)

    spec_requirements = extract_spec_requirements(spec_data)
    labelled_requirements = extract_labelled_requirements(coverage_data)

    return calculate_ambiguity_uncovered_coverage(
        spec_requirements=spec_requirements,
        labelled_requirements=labelled_requirements,
    )


def print_ambiguity_uncovered_summary(result: dict[str, Any]) -> None:
    print("\nAmbiguity-Related Uncovered Rate")
    print("--------------------------------")
    print(f"Total spec items:                    {result['total_spec_items']}")
    print(
        "Spec items uncovered due to ambiguity: "
        f"{result['spec_items_uncovered_due_to_ambiguity']}"
    )
    print("Other spec items:                       " f"{result['other_spec_items']}")
    print(
        f"Rate:                                   {result['ambiguity_uncovered_rate']}%"
    )

    if result["ambiguity_uncovered_requirements"]:
        print("\nRequirements uncovered due to ambiguity:")
        for requirement in result["ambiguity_uncovered_requirements"]:
            print(f"  - {requirement['requirement_id']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate the deterministic ambiguity-related uncovered rate."
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

    result = run_ambiguity_uncovered_coverage(
        spec_file=args.spec_file,
        coverage_file=args.coverage_file,
    )

    print_ambiguity_uncovered_summary(result)
