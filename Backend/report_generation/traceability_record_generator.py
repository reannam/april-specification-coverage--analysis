from pathlib import Path
import json
import csv
import argparse
from collections import defaultdict

from Backend.config import TRACEABILITY_DIR


def load_vplan(vplan_file: Path) -> dict:
    if not vplan_file.exists():
        raise FileNotFoundError(f"vPlan file not found: {vplan_file}")

    with vplan_file.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_vplan_rows(vplan_data: dict) -> list[dict]:
    if "feature_list" in vplan_data:
        return vplan_data["feature_list"]

    if "vplan" in vplan_data and "feature_list" in vplan_data["vplan"]:
        return vplan_data["vplan"]["feature_list"]

    raise ValueError("Could not find feature_list in the vPlan JSON file.")


def build_requirement_test_map(vplan_rows: list[dict]) -> dict[str, list[str]]:
    requirement_test_map = defaultdict(list)

    for row in vplan_rows:
        requirement_id = row.get("requirement_id")
        test_id = row.get("test_id")

        if not requirement_id or not test_id:
            continue

        requirement_test_map[requirement_id].append(test_id)

    return dict(requirement_test_map)


def export_requirement_test_links(vplan_file: Path) -> Path:
    vplan_data = load_vplan(vplan_file)
    vplan_rows = get_vplan_rows(vplan_data)

    requirement_test_map = build_requirement_test_map(vplan_rows)

    csv_file = TRACEABILITY_DIR / f"{vplan_file.stem}_requirement_test_links.csv"

    with csv_file.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["requirement_id", "related_tests"],
        )

        writer.writeheader()

        for requirement_id, test_ids in requirement_test_map.items():
            related_tests = {
                "test_ids": test_ids
            }

            writer.writerow({
                "requirement_id": requirement_id,
                "related_tests": json.dumps(related_tests),
            })

    return csv_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export requirement IDs and their related test IDs to CSV."
    )

    parser.add_argument(
        "vplan_file",
        type=Path,
        help="Path to the generated vPlan JSON file.",
    )

    args = parser.parse_args()

    csv_file = export_requirement_test_links(args.vplan_file)

    print(f"Requirement-test links CSV saved to: {csv_file}")


if __name__ == "__main__":
    main()