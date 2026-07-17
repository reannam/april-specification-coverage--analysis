from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from Backend.config import COVERAGE_TERMS_FILE
from Backend.text_config import load_grouped_text_config, require_groups

TERM_GROUPS, _ = load_grouped_text_config(COVERAGE_TERMS_FILE)
require_groups(
    TERM_GROUPS,
    {
        "covered_statuses",
        "partially_covered_statuses",
        "ambiguous_statuses",
        "not_covered_statuses",
    },
    source=COVERAGE_TERMS_FILE,
)

COVERED_STATUSES = TERM_GROUPS["covered_statuses"]
PARTIALLY_COVERED_STATUSES = TERM_GROUPS["partially_covered_statuses"]
AMBIGUOUS_STATUSES = TERM_GROUPS["ambiguous_statuses"]
NOT_COVERED_STATUSES = TERM_GROUPS["not_covered_statuses"]

# Fixed policy weights used only for coverage-state aggregation. They are not
# requirement importance, severity, or risk values.
COVERAGE_WEIGHTS = {
    "Covered": 1.0,
    "Partially covered": 0.5,
    "Uncovered": 0.0,
    "Ambiguous / not yet plannable": 0.0,
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
    normalised_status = str(status or "").strip().lower()

    if normalised_status in COVERED_STATUSES:
        return "Covered"

    if normalised_status in PARTIALLY_COVERED_STATUSES:
        return "Partially covered"

    if normalised_status in AMBIGUOUS_STATUSES:
        return "Ambiguous / not yet plannable"

    if normalised_status in NOT_COVERED_STATUSES:
        return "Uncovered"

    return "Uncovered"


def coverage_status_to_score(status: str | None) -> float:
    normalised_status = normalise_coverage_status(status)
    return COVERAGE_WEIGHTS.get(normalised_status, 0.0)


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

        coverage_reason = requirement.get("coverage_verification_reason")

        rows.append(
            {
                "requirement_id": requirement_id,
                "spec_statement": requirement.get("text"),
                "vplan_item_ids": requirement.get("linked_tests", []),
                "coverage_status": coverage_status,
                "coverage_score": coverage_score,
                "notes": coverage_reason or "",
            }
        )

    return rows


def calculate_overall_coverage_score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_score = sum(row["coverage_score"] for row in rows)

    overall_coverage_score = round((total_score / len(rows)) * 100, 2) if rows else 0.0

    status_counts: dict[str, int] = {}

    for row in rows:
        status = row["coverage_status"]

        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "formula": "sum(c_i) / N * 100, where c_i is 1, 0.5, or 0",
        "total_items": len(rows),
        "total_score": total_score,
        "overall_coverage_score": overall_coverage_score,
        "status_counts": status_counts,
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
            "scoring_method": "covered_1_partial_0.5_uncovered_0",
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
        "total_score": report["overall_coverage_summary"]["total_score"],
        "json_output_file": str(json_output_path),
        "csv_output_file": str(csv_output_path) if csv_output_path else None,
    }


def print_overall_coverage_summary(result: dict[str, Any]) -> None:
    print("\nOverall Spec-to-vPlan Coverage")
    print("------------------------------")
    print(f"Total items:             {result['total_items']}")
    print(f"Total score:             {result['total_score']}")
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
