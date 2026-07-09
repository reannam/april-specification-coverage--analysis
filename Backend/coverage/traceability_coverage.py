from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TRACEABILITY_FIELDS = [
    "requirement_id",
    "source_requirement_id",
    "source_section",
    "section",
    "section_id",
    "table_id",
    "figure_id",
    "rule_id",
    "page",
    "page_number",
    "paragraph",
    "source_reference",
    "source_refs",
    "traceability",
]


SECTION_PATTERN = re.compile(r"\b[A-Z]\d+(?:\.\d+)*\b")
REQUIREMENT_PATTERN = re.compile(r"\bREQ_[A-Z0-9_]+\b")
TABLE_PATTERN = re.compile(
    r"\bTABLE_[A-Z0-9_]+\b|\bTable\s+[A-Z]?\d+(?:\.\d+)*\b", re.IGNORECASE
)
FIGURE_PATTERN = re.compile(
    r"\bFIG_[A-Z0-9_]+\b|\bFigure\s+[A-Z]?\d+(?:\.\d+)*\b", re.IGNORECASE
)
PAGE_PATTERN = re.compile(r"\bpage\s+\d+\b", re.IGNORECASE)


def load_json(file_path: str | Path) -> dict[str, Any] | list[dict[str, Any]]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_vplan_items(
    vplan_data: dict[str, Any] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
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


def value_has_content(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, list):
        return any(value_has_content(item) for item in value)

    if isinstance(value, dict):
        return any(value_has_content(item) for item in value.values())

    return True


def field_contains_source_trace(vplan_item: dict[str, Any]) -> bool:
    for field in TRACEABILITY_FIELDS:
        if field in vplan_item and value_has_content(vplan_item[field]):
            return True

    return False


def text_contains_source_trace(vplan_item: dict[str, Any]) -> bool:
    """
    Fallback check for source traces embedded in free text fields.
    This catches values like:
    - A2.1
    - REQ_A2_1_001
    - Table A2.1
    - Figure A2.3
    - page 12
    """

    searchable_text = json.dumps(vplan_item, ensure_ascii=False)

    trace_patterns = [
        SECTION_PATTERN,
        REQUIREMENT_PATTERN,
        TABLE_PATTERN,
        FIGURE_PATTERN,
        PAGE_PATTERN,
    ]

    return any(pattern.search(searchable_text) for pattern in trace_patterns)


def has_source_trace(vplan_item: dict[str, Any]) -> bool:
    return field_contains_source_trace(vplan_item) or text_contains_source_trace(
        vplan_item
    )


def get_test_id(vplan_item: dict[str, Any], fallback_index: int) -> str:
    return str(
        vplan_item.get("test_id")
        or vplan_item.get("id")
        or f"VPLAN_ITEM_{fallback_index + 1:03d}"
    )


def calculate_traceability_coverage(
    vplan_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Traceability Coverage =
        number of vPlan items with source trace
        / total number of vPlan items
        * 100
    """

    total_vplan_items = len(vplan_items)

    traceable_items = []
    untraceable_items = []

    for index, item in enumerate(vplan_items):
        item_summary = {
            "vplan_index": index,
            "test_id": get_test_id(item, index),
            "requirement_id": item.get("requirement_id"),
            "source_section": item.get("source_section"),
        }

        if has_source_trace(item):
            traceable_items.append(item_summary)
        else:
            untraceable_items.append(item_summary)

    traceable_count = len(traceable_items)

    coverage_percentage = (
        round((traceable_count / total_vplan_items) * 100, 2)
        if total_vplan_items > 0
        else 0.0
    )

    return {
        "metric_name": "Traceability Coverage",
        "definition": "Percentage of vPlan items that cite their source requirement/section.",
        "formula": "(vplan_items_with_source_trace / total_vplan_items) * 100",
        "total_vplan_items": total_vplan_items,
        "vplan_items_with_source_trace": traceable_count,
        "vplan_items_without_source_trace": len(untraceable_items),
        "traceability_coverage": coverage_percentage,
        "traceable_items": traceable_items,
        "untraceable_items": untraceable_items,
    }


def run_traceability_coverage(vplan_file: str | Path) -> dict[str, Any]:
    vplan_data = load_json(vplan_file)
    vplan_items = extract_vplan_items(vplan_data)

    return calculate_traceability_coverage(vplan_items)


def print_traceability_summary(result: dict[str, Any]) -> None:
    print("\nTraceability Coverage")
    print("---------------------")
    print(f"Total vPlan items:              {result['total_vplan_items']}")
    print(f"vPlan items with source trace:  {result['vplan_items_with_source_trace']}")
    print(
        f"vPlan items without trace:      {result['vplan_items_without_source_trace']}"
    )
    print(f"Coverage:                       {result['traceability_coverage']}%")

    if result["untraceable_items"]:
        print("\nUntraceable vPlan items:")
        for item in result["untraceable_items"]:
            print(f"  - {item['test_id']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate deterministic traceability coverage."
    )

    parser.add_argument(
        "--vplan-file",
        required=True,
        help="Path to the generated vPlan JSON file.",
    )

    args = parser.parse_args()

    result = run_traceability_coverage(args.vplan_file)

    print_traceability_summary(result)
