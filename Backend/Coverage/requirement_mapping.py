from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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


def extract_vplan_items(vplan_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Supports:
    - {"feature_list": [...]}
    - {"table": {"feature_list": [...]}}
    - {"vplan": [...]}
    - raw list of vPlan rows
    """

    if isinstance(vplan_data, list):
        return vplan_data

    if isinstance(vplan_data.get("feature_list"), list):
        return vplan_data["feature_list"]

    if isinstance(vplan_data.get("table"), dict):
        feature_list = vplan_data["table"].get("feature_list")
        if isinstance(feature_list, list):
            return feature_list

    if isinstance(vplan_data.get("vplan"), list):
        return vplan_data["vplan"]

    raise ValueError(
        "Could not find vPlan items. Expected 'feature_list', 'table.feature_list', or 'vplan'."
    )


def get_requirement_id(item: dict[str, Any]) -> str | None:
    requirement_id = item.get("requirement_id") or item.get("id")

    if requirement_id is None:
        return None

    return str(requirement_id)


def calculate_requirement_mapping_coverage(
    spec_requirements: list[dict[str, Any]],
    vplan_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Requirement Mapping Coverage =
        number of spec items mapped to at least one vPlan item
        / total number of spec items
        * 100
    """

    total_spec_items = len(spec_requirements)

    vplan_requirement_ids = {
        get_requirement_id(item) for item in vplan_items if get_requirement_id(item)
    }

    mapped_requirement_ids = []
    unmapped_requirement_ids = []

    for requirement in spec_requirements:
        requirement_id = get_requirement_id(requirement)

        if requirement_id in vplan_requirement_ids:
            mapped_requirement_ids.append(requirement_id)
        else:
            unmapped_requirement_ids.append(requirement_id)

    mapped_count = len(mapped_requirement_ids)

    coverage_percentage = (
        round((mapped_count / total_spec_items) * 100, 2)
        if total_spec_items > 0
        else 0.0
    )

    return {
        "metric_name": "Requirement Mapping Coverage",
        "total_spec_items": total_spec_items,
        "spec_items_mapped_to_vplan": mapped_count,
        "spec_items_unmapped_to_vplan": len(unmapped_requirement_ids),
        "requirement_mapping_coverage": coverage_percentage,
        "mapped_requirement_ids": mapped_requirement_ids,
        "unmapped_requirement_ids": unmapped_requirement_ids,
    }


def run_requirement_mapping_coverage(
    spec_file: str | Path,
    vplan_file: str | Path,
) -> dict[str, Any]:
    spec_data = load_json(spec_file)
    vplan_data = load_json(vplan_file)

    spec_requirements = extract_spec_requirements(spec_data)
    vplan_items = extract_vplan_items(vplan_data)

    return calculate_requirement_mapping_coverage(
        spec_requirements=spec_requirements,
        vplan_items=vplan_items,
    )


def print_requirement_mapping_summary(result: dict[str, Any]) -> None:
    print("\nRequirement Mapping Coverage")
    print("----------------------------")
    print(f"Total spec items:            {result['total_spec_items']}")
    print(f"Spec items mapped to vPlan:  {result['spec_items_mapped_to_vplan']}")
    print(f"Spec items not mapped:       {result['spec_items_unmapped_to_vplan']}")
    print(f"Coverage:                    {result['requirement_mapping_coverage']}%")

    if result["unmapped_requirement_ids"]:
        print("\nUnmapped requirement IDs:")
        for requirement_id in result["unmapped_requirement_ids"]:
            print(f"  - {requirement_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate deterministic requirement mapping coverage."
    )

    parser.add_argument(
        "--spec-file",
        required=True,
        help="Path to the extracted spec JSON file.",
    )

    parser.add_argument(
        "--vplan-file",
        required=True,
        help="Path to the generated vPlan JSON file.",
    )

    args = parser.parse_args()

    result = run_requirement_mapping_coverage(
        spec_file=args.spec_file,
        vplan_file=args.vplan_file,
    )

    print_requirement_mapping_summary(result)
