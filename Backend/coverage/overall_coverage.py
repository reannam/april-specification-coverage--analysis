from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

COVERAGE_WEIGHTS = {
    "Covered": 1.0,
    "covered": 1.0,
    "Fully covered": 1.0,
    "fully_covered": 1.0,
    "Partially covered": 0.5,
    "partially_covered": 0.5,
    "Uncovered": 0.0,
    "uncovered": 0.0,
    "Not covered": 0.0,
    "not_covered": 0.0,
    "Ambiguous / not yet plannable": 0.0,
    "ambiguous": 0.0,
    "Blocked": 0.0,
    "blocked": 0.0,
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


def normalise_coverage_status(status: str | None) -> str:
    if status in {"Covered", "covered", "Fully covered", "fully_covered"}:
        return "Covered"

    if status in {"Partially covered", "partially_covered"}:
        return "Partially covered"

    if status in {"Ambiguous / not yet plannable", "ambiguous", "Ambiguous"}:
        return "Ambiguous / not yet plannable"

    return "Uncovered"


def coverage_status_to_score(status: str | None) -> float:
    normalised_status = normalise_coverage_status(status)
    return COVERAGE_WEIGHTS.get(normalised_status, 0.0)


def determine_requirement_weight(requirement: dict[str, Any]) -> tuple[int, str]:
    """
    Deterministically assign an importance weight to a requirement.

    Weight meanings:
    - 3 = critical protocol rule / mandatory behaviour
    - 2 = important functional or conditional behaviour
    - 1 = optional / secondary / explanatory detail
    """

    text = str(requirement.get("text", "")).lower()
    req_type = str(requirement.get("type", "")).lower()
    source_section = str(requirement.get("source_section", "")).lower()

    critical_terms = [
        "must",
        "shall",
        "required",
        "not permitted",
        "must not",
        "shall not",
        "cannot",
        "only",
        "always",
        "no ",
        "must be",
        "must not be",
    ]

    optional_terms = [
        "may",
        "can be",
        "permitted",
        "optional",
        "recommended",
        "not required",
        "is permitted",
        "are permitted",
    ]

    explanatory_terms = [
        "for example",
        "example",
        "cycle",
        "this can occur",
        "in this case",
        "description",
        "indicates",
        "figure",
        "shown in",
    ]

    important_functional_terms = [
        "transfer",
        "transaction",
        "handshake",
        "valid",
        "ready",
        "credit",
        "reset",
        "response",
        "data",
        "request",
        "signal",
        "manager",
        "subordinate",
        "interconnect",
        "channel",
        "assert",
        "deassert",
    ]

    # 1. Example / explanatory text should not dominate the overall score.
    if any(term in text for term in explanatory_terms):
        return (
            1,
            "Assigned weight 1 because the requirement appears to be explanatory, example-based, or cycle-specific detail.",
        )

    # 2. Optional / permitted behaviour is usually secondary unless also expressed as mandatory.
    # Check this before broad functional terms, but after explanatory terms.
    if any(term in text for term in optional_terms) and not any(
        term in text for term in ["must", "shall", "required", "must not", "shall not"]
    ):
        return (
            1,
            "Assigned weight 1 because the requirement describes optional or permitted behaviour.",
        )

    # 3. Mandatory/prohibitive protocol language is critical.
    if any(term in text for term in critical_terms):
        return (
            3,
            "Assigned weight 3 because the requirement contains mandatory or prohibitive protocol language.",
        )

    # 4. Functional protocol behaviour is important even if wording is not strictly mandatory.
    if req_type in {"protocol_rule", "encoding_rule"} and any(
        term in text for term in important_functional_terms
    ):
        return (
            2,
            "Assigned weight 2 because the requirement describes important protocol behaviour but is not expressed as a strict mandatory rule.",
        )

    # 5. A2 is the target section, so default to medium if it is functionally relevant.
    if source_section.startswith("a2"):
        return (
            2,
            "Assigned weight 2 because the requirement belongs to the target protocol section and appears functionally relevant.",
        )

    return (
        1,
        "Assigned weight 1 because no stronger deterministic importance signal was found.",
    )


def build_overall_coverage_rows(
    labelled_requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []

    for requirement in labelled_requirements:
        requirement_id = requirement.get("id") or requirement.get("requirement_id")

        coverage_status = normalise_coverage_status(
            requirement.get("verified_coverage_status")
        )
        coverage_score = coverage_status_to_score(coverage_status)

        importance_weight, weight_reason = determine_requirement_weight(requirement)

        weighted_score = coverage_score * importance_weight

        coverage_reason = requirement.get("coverage_verification_reason")

        notes_parts = []

        if coverage_reason:
            notes_parts.append(coverage_reason)

        notes_parts.append(weight_reason)

        rows.append(
            {
                "requirement_id": requirement_id,
                "spec_statement": requirement.get("text"),
                "vplan_item_ids": requirement.get("linked_tests", []),
                "coverage_status": coverage_status,
                "coverage_score": coverage_score,
                "importance_weight": importance_weight,
                "weighted_score": weighted_score,
                "notes": " ".join(notes_parts),
            }
        )

    return rows


def calculate_overall_coverage_score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_weight = sum(row["importance_weight"] for row in rows)
    total_weighted_score = sum(row["weighted_score"] for row in rows)

    overall_coverage_score = (
        round((total_weighted_score / total_weight) * 100, 2)
        if total_weight > 0
        else 0.0
    )

    status_counts: dict[str, int] = {}
    weight_counts: dict[str, int] = {}

    for row in rows:
        status = row["coverage_status"]
        weight = str(row["importance_weight"])

        status_counts[status] = status_counts.get(status, 0) + 1
        weight_counts[weight] = weight_counts.get(weight, 0) + 1

    return {
        "formula": "sum(w_i * c_i) / sum(w_i) * 100",
        "total_items": len(rows),
        "total_weight": total_weight,
        "total_weighted_score": total_weighted_score,
        "overall_coverage_score": overall_coverage_score,
        "status_counts": status_counts,
        "importance_weight_counts": weight_counts,
    }


def build_overall_coverage_report(coverage_file: str | Path) -> dict[str, Any]:
    coverage_data = load_json(coverage_file)
    labelled_requirements = extract_labelled_requirements(coverage_data)

    rows = build_overall_coverage_rows(labelled_requirements)
    summary = calculate_overall_coverage_score(rows)

    return {
        "metadata": {
            "date_created": datetime.now().strftime("%B %d %Y"),
            "time_created": datetime.now().strftime("%I:%M%p").lower(),
            "coverage_file": str(coverage_file),
            "weighting_method": "deterministic_keyword_rules_v1",
        },
        "overall_coverage_summary": summary,
        "coverage_table": rows,
    }


def save_json_report(report: dict[str, Any], output_file: str | Path) -> Path:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    return output_path


def save_csv_table(report: dict[str, Any], csv_file: str | Path) -> Path:
    csv_path = Path(csv_file)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    rows = report["coverage_table"]

    fieldnames = [
        "requirement_id",
        "spec_statement",
        "vplan_item_ids",
        "coverage_status",
        "coverage_score",
        "importance_weight",
        "weighted_score",
        "notes",
        "overall_coverage_score",
    ]

    overall_score = report["overall_coverage_summary"]["overall_coverage_score"]

    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    "requirement_id": row["requirement_id"],
                    "spec_statement": row["spec_statement"],
                    "vplan_item_ids": ", ".join(row.get("vplan_item_ids", [])),
                    "coverage_status": row["coverage_status"],
                    "coverage_score": row["coverage_score"],
                    "importance_weight": row["importance_weight"],
                    "weighted_score": row["weighted_score"],
                    "notes": row["notes"],
                    "overall_coverage_score": overall_score,
                }
            )

    return csv_path


def run_overall_coverage(
    coverage_file: str | Path,
    output_file: str | Path,
    csv_file: str | Path | None = None,
) -> dict[str, Any]:
    report = build_overall_coverage_report(coverage_file)

    json_output_path = save_json_report(report, output_file)

    csv_output_path = None
    if csv_file is not None:
        csv_output_path = save_csv_table(report, csv_file)

    return {
        "overall_coverage_score": report["overall_coverage_summary"][
            "overall_coverage_score"
        ],
        "total_items": report["overall_coverage_summary"]["total_items"],
        "total_weight": report["overall_coverage_summary"]["total_weight"],
        "total_weighted_score": report["overall_coverage_summary"][
            "total_weighted_score"
        ],
        "json_output_file": str(json_output_path),
        "csv_output_file": str(csv_output_path) if csv_output_path else None,
    }


def print_overall_coverage_summary(result: dict[str, Any]) -> None:
    print("\nOverall Spec-to-vPlan Coverage")
    print("------------------------------")
    print(f"Total items:             {result['total_items']}")
    print(f"Total weight:            {result['total_weight']}")
    print(f"Total weighted score:    {result['total_weighted_score']}")
    print(f"Overall coverage score:  {result['overall_coverage_score']}%")
    print(f"JSON summary file:       {result['json_output_file']}")

    if result["csv_output_file"]:
        print(f"CSV table file:          {result['csv_output_file']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate deterministic overall weighted Spec-to-vPlan coverage."
    )

    parser.add_argument(
        "--coverage-file",
        required=True,
        help="Path to the output JSON from coverage_status_verifier.py.",
    )

    parser.add_argument(
        "--output-file",
        required=True,
        help="Path where the overall coverage JSON summary should be written.",
    )

    parser.add_argument(
        "--csv-file",
        required=False,
        help="Optional path where a CSV coverage table should be written.",
    )

    args = parser.parse_args()

    result = run_overall_coverage(
        coverage_file=args.coverage_file,
        output_file=args.output_file,
        csv_file=args.csv_file,
    )

    print_overall_coverage_summary(result)
