import argparse
import json

from Backend.coverage_workflow import build_coverage_workflow


def main():
    parser = argparse.ArgumentParser(
        description="Run coverage analysis using a requirements JSON file and generated vPlan JSON file."
    )

    parser.add_argument(
        "--requirements",
        required=True,
        help="Path to the source requirements JSON file.",
    )

    parser.add_argument(
        "--vplan",
        required=True,
        help="Path to the generated vPlan JSON file.",
    )

    args = parser.parse_args()

    chain = build_coverage_workflow()

    result = chain.invoke(
        {
            "requirements_file": args.requirements,
            "vplan_file": args.vplan,
        }
    )

    print("\nCoverage analysis complete.")
    print(f"Output file: {result.get('coverage_output_file')}")

    print("\nSummary:")
    print(json.dumps(result.get("coverage_report", {}).get("summary", {}), indent=2))

    validation_errors = result.get("coverage_validation_errors", [])
    if validation_errors:
        print("\nValidation warnings:")
        for error in validation_errors:
            print(f"- {error}")

    missing_requirement_ids = result.get("coverage_missing_requirement_ids", [])
    if missing_requirement_ids:
        print("\nRequirements missing from vPlan:")
        for requirement_id in missing_requirement_ids:
            print(f"- {requirement_id}")


if __name__ == "__main__":
    main()