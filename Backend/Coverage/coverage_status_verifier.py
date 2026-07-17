from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from Backend.config import COVERAGE_STATUS_DIR
from Backend.Coverage.related_requirements import (
    index_requirements,
    resolve_supporting_requirements,
)

REQUIREMENT_STATUSES = {
    "covered": "Covered",
    "partially_covered": "Partially covered",
    "uncovered": "Uncovered",
    "ambiguous_not_yet_plannable": "Ambiguous / not yet plannable",
}

VPLAN_COVERAGE_VALUES = {
    "covered",
    "partially_covered",
    "uncovered",
}


def build_duplicate_requirement_id_warning(
    requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Detect duplicate requirement IDs and return a validation warning block.

    This does not modify the requirements.
    It only reports duplicate IDs so downstream traceability can be treated as unreliable.
    """

    id_counts = Counter(req.get("id") for req in requirements if req.get("id"))

    duplicate_ids = sorted(req_id for req_id, count in id_counts.items() if count > 1)

    if not duplicate_ids:
        return []

    duplicate_details = defaultdict(list)

    for req in requirements:
        req_id = req.get("id")

        if req_id in duplicate_ids:
            duplicate_details[req_id].append(
                {
                    "source_section": req.get("source_section"),
                    "text": req.get("text"),
                }
            )

    return [
        {
            "warning_type": "duplicate_requirement_ids",
            "message": (
                "Duplicate requirement IDs were detected in the extracted requirements. "
                "Coverage traceability may be unreliable until requirement IDs are made unique."
            ),
            "affected_requirement_ids": duplicate_ids,
            "duplicate_details": dict(duplicate_details),
        }
    ]


def load_json(file_path: str | Path) -> Any:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: Any, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def extract_requirements(spec_json: Any) -> list[dict[str, Any]]:
    if isinstance(spec_json, list):
        return spec_json

    if isinstance(spec_json, dict):
        if isinstance(spec_json.get("requirements"), list):
            return spec_json["requirements"]

        if isinstance(spec_json.get("feature_list"), list):
            return spec_json["feature_list"]

    raise ValueError(
        "Could not find requirements. Expected a list, "
        "or a JSON object containing 'requirements' or 'feature_list'."
    )


def extract_vplan_tests(vplan_json: Any) -> list[dict[str, Any]]:
    if isinstance(vplan_json, list):
        return vplan_json

    if isinstance(vplan_json, dict):
        if isinstance(vplan_json.get("feature_list"), list):
            return vplan_json["feature_list"]

        if isinstance(vplan_json.get("tests"), list):
            return vplan_json["tests"]

    raise ValueError(
        "Could not find vPlan tests. Expected a list, "
        "or a JSON object containing 'feature_list' or 'tests'."
    )


def extract_items(items_json: Any) -> list[dict[str, Any]]:
    """
    Generic extractor for edge cases and weak-word outputs.
    """

    if not items_json:
        return []

    if isinstance(items_json, list):
        return [item for item in items_json if isinstance(item, dict)]

    if isinstance(items_json, dict):
        for key in [
            "feature_list",
            "edge_cases",
            "weak_requirements",
            "flagged_requirements",
            "issues",
            "results",
        ]:
            if isinstance(items_json.get(key), list):
                return [item for item in items_json[key] if isinstance(item, dict)]

    return []


def get_requirement_id(item: dict[str, Any]) -> str | None:
    for key in ["requirement_id", "id", "req_id"]:
        value = item.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def get_test_coverage(test: dict[str, Any]) -> str | None:
    """
    Reads the original coverage label produced by the vPlan agent.

    Supports:
    - coverage
    - test_coverage
    - status
    """

    for key in ["coverage", "test_coverage", "status"]:
        value = test.get(key)

        if isinstance(value, str):
            normalised = value.strip().lower()

            if normalised in VPLAN_COVERAGE_VALUES:
                return normalised

    return None


def has_complete_test_content(test: dict[str, Any]) -> bool:
    """Return true only for a concrete, executable row with observable evidence."""

    description = test.get("test_description")
    steps = test.get("test_steps")
    expected_results = test.get("expected_results")

    return (
        isinstance(description, str)
        and bool(description.strip())
        and isinstance(steps, list)
        and any(isinstance(step, str) and step.strip() for step in steps)
        and isinstance(expected_results, list)
        and any(
            isinstance(result, str) and result.strip() for result in expected_results
        )
    )


def group_by_requirement_id(
    items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for item in items:
        requirement_id = get_requirement_id(item)

        if not requirement_id:
            continue

        grouped.setdefault(requirement_id, []).append(item)

    return grouped


def classify_requirement_status(
    requirement_id: str,
    linked_tests: list[dict[str, Any]],
    linked_edge_cases: list[dict[str, Any]],
    linked_weak_word_flags: list[dict[str, Any]],
) -> tuple[str, str]:
    """
    Verifies the original vPlan coverage labels at requirement level.

    Rule summary:
    A vPlan label is evidence, not authority. A requirement is only Covered when
    every linked row is complete, every row is labelled covered, and no linked
    ambiguity evidence exists. Traceability-only or incomplete rows never count
    as executable tests.
    """

    has_rows = len(linked_tests) > 0
    has_edge_cases = len(linked_edge_cases) > 0
    has_weak_word_flags = len(linked_weak_word_flags) > 0
    has_ambiguity_signals = has_edge_cases or has_weak_word_flags

    if not has_rows and has_ambiguity_signals:
        return (
            REQUIREMENT_STATUSES["ambiguous_not_yet_plannable"],
            "Requirement has no generated tests and has linked weak-word or edge-case signals.",
        )

    if not has_rows:
        return (
            REQUIREMENT_STATUSES["uncovered"],
            "Requirement has no generated tests.",
        )

    complete_tests = [
        test
        for test in linked_tests
        if has_complete_test_content(test) and get_test_coverage(test) != "uncovered"
    ]
    complete_coverage_values = [
        coverage
        for test in complete_tests
        if (coverage := get_test_coverage(test)) is not None
    ]
    incomplete_row_count = len(linked_tests) - len(complete_tests)

    if not complete_tests:
        if has_ambiguity_signals:
            return (
                REQUIREMENT_STATUSES["ambiguous_not_yet_plannable"],
                "No linked row contains a complete executable test and observable expected result; ambiguity evidence is also present.",
            )

        return (
            REQUIREMENT_STATUSES["uncovered"],
            "No linked row contains a complete executable test and observable expected result.",
        )

    all_rows_complete = incomplete_row_count == 0
    all_labels_present = len(complete_coverage_values) == len(complete_tests)
    all_explicitly_covered = all(
        value == "covered" for value in complete_coverage_values
    )

    if (
        all_rows_complete
        and all_labels_present
        and all_explicitly_covered
        and not has_ambiguity_signals
    ):
        return (
            REQUIREMENT_STATUSES["covered"],
            "Every linked row contains a complete executable test, every row is marked covered, and no linked ambiguity evidence was found.",
        )

    reasons = []
    if incomplete_row_count:
        reasons.append(
            f"{incomplete_row_count} linked row(s) lack complete executable test content"
        )
    if not all_labels_present:
        reasons.append(
            "one or more complete tests have no recognised vPlan coverage label"
        )
    if any(value == "partially_covered" for value in complete_coverage_values):
        reasons.append("one or more complete tests are marked partially covered")
    if any(value == "uncovered" for value in complete_coverage_values):
        reasons.append("one or more linked rows are marked uncovered")
    if has_ambiguity_signals:
        reasons.append("weak-language or edge-case evidence is linked")

    return (
        REQUIREMENT_STATUSES["partially_covered"],
        "At least one concrete test is available, but full coverage is not justified because "
        + "; ".join(reasons or ["the linked evidence is incomplete"])
        + ".",
    )


def verify_requirement_coverage(
    spec_json: Any,
    vplan_json: Any,
    edge_cases_json: Any,
    weak_words_json: Any,
) -> dict[str, Any]:
    """Produce the authoritative requirement-level status used by final reports.

    vPlan labels are retained for auditability, but they are not trusted on their
    own: executable content and linked ambiguity evidence are checked again here.
    """

    requirements = extract_requirements(spec_json)
    requirements_by_id = index_requirements(requirements)
    vplan_tests = extract_vplan_tests(vplan_json)
    edge_cases = extract_items(edge_cases_json)
    weak_word_flags = extract_items(weak_words_json)

    tests_by_requirement = group_by_requirement_id(vplan_tests)
    edge_cases_by_requirement = group_by_requirement_id(edge_cases)
    weak_words_by_requirement = group_by_requirement_id(weak_word_flags)

    labelled_requirements: list[dict[str, Any]] = []
    traceability: list[dict[str, Any]] = []
    uncovered_test_report: list[dict[str, Any]] = []

    status_counts: Counter[str] = Counter()

    for requirement in requirements:
        requirement_id = get_requirement_id(requirement)

        if not requirement_id:
            status = REQUIREMENT_STATUSES["ambiguous_not_yet_plannable"]
            reason = "Requirement has no identifiable requirement ID."

            labelled_requirements.append(
                {
                    **requirement,
                    "verified_coverage_status": status,
                    "coverage_verification_reason": reason,
                    "linked_tests": [],
                    "linked_edge_cases": [],
                    "linked_weak_word_flags": [],
                }
            )

            status_counts[status] += 1
            continue

        linked_tests = tests_by_requirement.get(requirement_id, [])
        linked_edge_cases = edge_cases_by_requirement.get(requirement_id, [])
        linked_weak_word_flags = weak_words_by_requirement.get(requirement_id, [])

        status, reason = classify_requirement_status(
            requirement_id=requirement_id,
            linked_tests=linked_tests,
            linked_edge_cases=linked_edge_cases,
            linked_weak_word_flags=linked_weak_word_flags,
        )

        status_counts[status] += 1

        linked_test_ids = [
            test.get("test_id")
            for test in linked_tests
            if isinstance(test.get("test_id"), str)
        ]
        linked_supporting_requirement_ids = sorted(
            {
                str(supporting_id)
                for test in linked_tests
                for supporting_id in test.get("supporting_requirement_ids", [])
                if supporting_id
            }
        )
        linked_supporting_requirements = resolve_supporting_requirements(
            requirement_id,
            linked_tests,
            requirements_by_id,
        )
        invalid_supporting_requirement_ids = sorted(
            supporting_id
            for supporting_id in linked_supporting_requirement_ids
            if supporting_id not in requirements_by_id
        )

        original_vplan_coverage_values = [
            get_test_coverage(test)
            for test in linked_tests
            if get_test_coverage(test) is not None
        ]

        labelled_requirements.append(
            {
                **requirement,
                "verified_coverage_status": status,
                "coverage_verification_reason": reason,
                "original_vplan_coverage_values": original_vplan_coverage_values,
                "linked_tests": linked_test_ids,
                "linked_supporting_requirement_ids": linked_supporting_requirement_ids,
                "linked_supporting_requirements": linked_supporting_requirements,
                "invalid_supporting_requirement_ids": (
                    invalid_supporting_requirement_ids
                ),
                "linked_edge_cases": linked_edge_cases,
                "linked_weak_word_flags": linked_weak_word_flags,
            }
        )

        traceability.append(
            {
                "requirement_id": requirement_id,
                "linked_test_ids": linked_test_ids,
                "linked_supporting_requirement_ids": linked_supporting_requirement_ids,
                "linked_supporting_requirements": linked_supporting_requirements,
                "invalid_supporting_requirement_ids": (
                    invalid_supporting_requirement_ids
                ),
                "original_vplan_coverage_values": original_vplan_coverage_values,
                "verified_coverage_status": status,
                "has_edge_case_flags": len(linked_edge_cases) > 0,
                "has_weak_word_flags": len(linked_weak_word_flags) > 0,
            }
        )

        if status in {
            REQUIREMENT_STATUSES["ambiguous_not_yet_plannable"],
            REQUIREMENT_STATUSES["uncovered"],
        }:
            uncovered_test_report.append(
                {
                    "requirement_id": requirement_id,
                    "uncovered_reason": reason,
                    "linked_tests": linked_test_ids,
                    "original_vplan_coverage_values": original_vplan_coverage_values,
                    "edge_cases": linked_edge_cases,
                    "weak_word_flags": linked_weak_word_flags,
                }
            )

    return {
        "metadata": {
            "date_created": datetime.now().strftime("%B %d %Y"),
            "time_created": datetime.now().strftime("%I:%M%p").lower(),
            "number_of_requirements": len(labelled_requirements),
            "number_of_vplan_tests": len(vplan_tests),
            "status_counts": dict(status_counts),
        },
        "labelled_requirements": labelled_requirements,
        "traceability": traceability,
        "uncovered_test_report": uncovered_test_report,
    }


def run_coverage_status_verifier(
    spec_file: str | Path,
    vplan_file: str | Path,
    edge_case_file: str | Path,
    weak_words_file: str | Path,
    output_file: str | Path,
) -> dict[str, Any]:
    output = verify_requirement_coverage(
        spec_json=load_json(spec_file),
        vplan_json=load_json(vplan_file),
        edge_cases_json=load_json(edge_case_file),
        weak_words_json=load_json(weak_words_file),
    )

    save_json(output, output_file)

    return {
        "coverage_status_file": str(output_file),
        "coverage_status_result": output,
        "usage": {},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify vPlan coverage labels against spec, edge cases, and weak-word results."
    )

    parser.add_argument(
        "--spec",
        required=True,
        help="Path to the original extracted JSON specification file.",
    )

    parser.add_argument(
        "--vplan",
        required=True,
        help="Path to the generated vPlan JSON file.",
    )

    parser.add_argument(
        "--edge-cases",
        required=True,
        help="Path to the generated edge-case JSON file.",
    )

    parser.add_argument(
        "--weak-words",
        required=True,
        help="Path to the weak-word checker JSON file.",
    )

    parser.add_argument(
        "--output",
        required=False,
        default=None,
        help="Output path for verified coverage status JSON.",
    )

    args = parser.parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = args.output or (
        COVERAGE_STATUS_DIR / f"verified_coverage_status_{timestamp}.json"
    )

    output = verify_requirement_coverage(
        spec_json=load_json(args.spec),
        vplan_json=load_json(args.vplan),
        edge_cases_json=load_json(args.edge_cases),
        weak_words_json=load_json(args.weak_words),
    )

    save_json(output, output_path)

    print(f"Verified coverage status saved to: {output_path}")


if __name__ == "__main__":
    main()
