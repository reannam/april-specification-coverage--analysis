import json
from collections import Counter

from Backend.vPlan.report_generation.weak_language_check import unwrap_requirements


def check_traceability(requirements_file: str, generated_vplan_file: str) -> None:
    """Check that generated vPlan rows trace back to input requirement IDs."""

    with open(requirements_file, "r", encoding="utf-8") as file:
        requirements_data = json.load(file)

    requirements = unwrap_requirements(requirements_data)

    with open(generated_vplan_file, "r", encoding="utf-8") as file:
        generated_vplan = json.load(file)

    vplan_rows = generated_vplan.get("feature_list", [])

    input_requirement_ids = {
        requirement.get("id")
        for requirement in requirements
        if isinstance(requirement, dict) and requirement.get("id")
    }

    output_requirement_ids = {
        row.get("requirement_id")
        for row in vplan_rows
        if isinstance(row, dict) and row.get("requirement_id")
    }

    missing = input_requirement_ids - output_requirement_ids
    extra = output_requirement_ids - input_requirement_ids

    requirement_test_counts = Counter(
        row.get("requirement_id")
        for row in vplan_rows
        if isinstance(row, dict) and row.get("requirement_id")
    )

    test_id_counts = Counter(
        row.get("test_id")
        for row in vplan_rows
        if isinstance(row, dict) and row.get("test_id")
    )

    duplicate_test_ids = {
        test_id: count for test_id, count in test_id_counts.items() if count > 1
    }

    requirements_with_multiple_tests = {
        requirement_id: count
        for requirement_id, count in requirement_test_counts.items()
        if count > 1
    }

    requirements_missing_ids = [
        requirement
        for requirement in requirements
        if not isinstance(requirement, dict) or not requirement.get("id")
    ]

    vplan_rows_missing_ids = [
        row
        for row in vplan_rows
        if not isinstance(row, dict) or not row.get("requirement_id")
    ]

    print("\nTraceability sanity check")
    print("-------------------------")
    print(f"Input requirements: {len(input_requirement_ids)}")
    print(f"Output vPlan rows/tests: {len(vplan_rows)}")
    print(f"Output vPlan requirement IDs: {len(output_requirement_ids)}")

    if requirements_missing_ids:
        print(
            f"\nWarning: {len(requirements_missing_ids)} input requirements are missing IDs."
        )

    if vplan_rows_missing_ids:
        print(
            f"Warning: {len(vplan_rows_missing_ids)} vPlan rows are missing requirement IDs."
        )

    if missing:
        print("\nMissing requirement IDs:")
        for requirement_id in sorted(missing, key=str):
            print(f"- {requirement_id}")
    else:
        print("\nNo missing requirement IDs.")

    if extra:
        print("\nUnexpected requirement IDs:")
        for requirement_id in sorted(extra, key=str):
            print(f"- {requirement_id}")
    else:
        print("No unexpected requirement IDs.")

    if duplicate_test_ids:
        print("\nDuplicate test IDs:")
        for test_id, count in sorted(
            duplicate_test_ids.items(), key=lambda item: str(item[0])
        ):
            print(f"- {test_id}: appears {count} times")
    else:
        print("No duplicate test IDs.")

    if requirements_with_multiple_tests:
        print("\nRequirement IDs with multiple atomic tests:")
        for requirement_id, count in sorted(
            requirements_with_multiple_tests.items(),
            key=lambda item: str(item[0]),
        ):
            print(f"- {requirement_id}: has {count} tests")
    else:
        print("No requirement IDs have multiple tests.")

    if not missing and not extra and not duplicate_test_ids:
        print("\nTraceability check passed.")
    else:
        print("\nTraceability check failed.")


def add_requirement_text(vplan_data: dict, requirements) -> dict:
    """Add original requirement text to each vPlan row."""

    requirements = unwrap_requirements(requirements)

    requirement_lookup = {
        requirement.get("id"): requirement.get("text", "")
        for requirement in requirements
        if isinstance(requirement, dict) and requirement.get("id")
    }

    for row in vplan_data.get("feature_list", []):
        if not isinstance(row, dict):
            continue

        requirement_id = row.get("requirement_id")
        row["requirement_text"] = requirement_lookup.get(requirement_id, "")

    return vplan_data
