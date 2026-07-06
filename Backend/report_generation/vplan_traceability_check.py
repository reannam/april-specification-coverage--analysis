import json
from collections import Counter

from Backend.report_generation.weak_language_check import unwrap_requirements

def check_traceability(requirements_file: str, generated_vplan_file: str) -> None:
    """Check that generated vPlan rows trace back to input requirement IDs."""

    with open(requirements_file, "r", encoding="utf-8") as file:
        requirements_data = json.load(file)

    requirements = unwrap_requirements(requirements_data)

    with open(generated_vplan_file, "r", encoding="utf-8") as file:
        generated_vplan = json.load(file)

    vplan_rows = generated_vplan["feature_list"]

    input_requirement_ids = {
        requirement["id"]
        for requirement in requirements
    }

    output_requirement_ids = {
        row["requirement_id"]
        for row in vplan_rows
    }

    missing = input_requirement_ids - output_requirement_ids
    extra = output_requirement_ids - input_requirement_ids

    requirement_test_counts = Counter(
        row["requirement_id"]
        for row in vplan_rows
    )

    test_id_counts = Counter(
        row["test_id"]
        for row in vplan_rows
    )

    duplicate_test_ids = {
        test_id: count
        for test_id, count in test_id_counts.items()
        if count > 1
    }

    requirements_with_multiple_tests = {
        requirement_id: count
        for requirement_id, count in requirement_test_counts.items()
        if count > 1
    }

    print("\nTraceability sanity check")
    print("-------------------------")
    print(f"Input requirements: {len(input_requirement_ids)}")
    print(f"Output vPlan rows/tests: {len(vplan_rows)}")
    print(f"Output vPlan requirement IDs: {len(output_requirement_ids)}")

    if missing:
        print("\nMissing requirement IDs:")
        for requirement_id in sorted(missing):
            print(f"- {requirement_id}")
    else:
        print("\nNo missing requirement IDs.")

    if extra:
        print("\nUnexpected requirement IDs:")
        for requirement_id in sorted(extra):
            print(f"- {requirement_id}")
    else:
        print("No unexpected requirement IDs.")

    if duplicate_test_ids:
        print("\nDuplicate test IDs:")
        for test_id, count in sorted(duplicate_test_ids.items()):
            print(f"- {test_id}: appears {count} times")
    else:
        print("No duplicate test IDs.")

    if requirements_with_multiple_tests:
        print("\nRequirement IDs with multiple atomic tests:")
        for requirement_id, count in sorted(requirements_with_multiple_tests.items()):
            print(f"- {requirement_id}: has {count} tests")
    else:
        print("No requirement IDs have multiple tests.")

    if not missing and not extra and not duplicate_test_ids:
        print("\nTraceability check passed.")
    else:
        print("\nTraceability check failed.")


def add_requirement_text(vplan_data: dict, requirements) -> dict:
    """Add requirement description and original text to each vPlan row."""

    requirements = unwrap_requirements(requirements)

    requirement_lookup = {
        requirement["id"]: {
            "requirement_text": requirement.get("text", ""),
        }
        for requirement in requirements
    }

    for row in vplan_data["feature_list"]:
        requirement_id = row["requirement_id"]
        requirement_data = requirement_lookup.get(requirement_id, {})

        row["requirement_text"] = requirement_data.get("requirement_text", "")

    return vplan_data