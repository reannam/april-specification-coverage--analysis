from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from Backend.coverage.coverage_workflow import run_coverage_workflow

load_dotenv()


def print_workflow_summary(result: dict[str, Any]) -> None:
    print("\nCoverage workflow complete")
    print("--------------------------")

    print(f"vPlan file:            {result.get('vplan_file')}")
    print(f"edge case file:        {result.get('edge_case_file')}")
    print(f"weak words file:       {result.get('weak_words_file')}")
    print(f"coverage status file:  {result.get('coverage_status_file')}")

    final_files = result.get("final_coverage_output_files", {})

    if final_files:
        print("\nFinal coverage outputs:")
        for label, path in final_files.items():
            print(f"  {label}: {path}")

    final_report = result.get("final_coverage_report")

    if final_report:
        coverage_summary = final_report.get("coverage_summary", {})
        coverage_percentages = final_report.get("coverage_percentages", {})

        print("\nCoverage summary:")
        print(f"  Total spec items:      {coverage_summary.get('total_spec_items')}")
        print(f"  Covered:               {coverage_summary.get('covered')}")
        print(f"  Partially covered:     {coverage_summary.get('partially_covered')}")
        print(f"  Uncovered:             {coverage_summary.get('uncovered')}")
        print(f"  Ambiguity-blocked:     {coverage_summary.get('ambiguity_blocked')}")
        print(f"  Orphan vPlan items:    {coverage_summary.get('orphan_vplan_items')}")

        print("\nCoverage percentages:")
        print(
            "  Requirement mapping:   "
            f"{coverage_percentages.get('requirement_mapping_coverage')}%"
        )
        print(
            "  Weighted coverage:     "
            f"{coverage_percentages.get('weighted_coverage')}%"
        )
        print(
            "  Traceability:          "
            f"{coverage_percentages.get('traceability_coverage')}%"
        )
        print(
            "  Testability:           "
            f"{coverage_percentages.get('testability_coverage')}%"
        )
        print("  Orphan rate:           " f"{coverage_percentages.get('orphan_rate')}%")

    total_usage = result.get("total_usage")

    if total_usage:
        print("\nTotal usage:")
        print(json.dumps(total_usage, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full coverage workflow.")

    parser.add_argument(
        "--requirements-file",
        required=True,
        help="Path to extracted spec / requirements JSON file.",
    )

    args = parser.parse_args()

    requirements_file = Path(args.requirements_file)

    if not requirements_file.exists():
        raise FileNotFoundError(f"Requirements file not found: {requirements_file}")

    result = run_coverage_workflow(str(requirements_file))

    print_workflow_summary(result)


if __name__ == "__main__":
    main()
