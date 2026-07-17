from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from Backend.config import COVERAGE_TERMS_FILE
from Backend.text_config import load_grouped_text_config, require_groups

TERM_GROUPS, REGEX_PATTERNS = load_grouped_text_config(COVERAGE_TERMS_FILE)
require_groups(
    TERM_GROUPS,
    {"traceability_fields", "regex_patterns"},
    source=COVERAGE_TERMS_FILE,
)

TRACEABILITY_FIELDS = TERM_GROUPS["traceability_fields"]

SECTION_PATTERN = re.compile(REGEX_PATTERNS["section"])
REQUIREMENT_PATTERN = re.compile(REGEX_PATTERNS["requirement"])
TABLE_PATTERN = re.compile(
    REGEX_PATTERNS["table"],
    re.IGNORECASE,
)
FIGURE_PATTERN = re.compile(
    REGEX_PATTERNS["figure"],
    re.IGNORECASE,
)


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


def extract_spec_sources(spec_data: dict[str, Any]) -> dict[str, set[str]]:
    requirements = spec_data.get("requirements", [])
    sections = spec_data.get("sections", [])
    tables = spec_data.get("tables", [])
    figures = spec_data.get("figures", [])
    pages = spec_data.get("pages", [])

    if not isinstance(requirements, list):
        requirements = []

    if not isinstance(sections, list):
        sections = []

    if not isinstance(tables, list):
        tables = []

    if not isinstance(figures, list):
        figures = []

    if not isinstance(pages, list):
        pages = []

    requirement_ids = {str(req.get("id")) for req in requirements if req.get("id")}

    section_ids = {str(section.get("id")) for section in sections if section.get("id")}

    table_ids = {str(table.get("id")) for table in tables if table.get("id")}

    figure_ids = {str(figure.get("id")) for figure in figures if figure.get("id")}

    page_numbers = {
        str(page.get("page_number"))
        for page in pages
        if page.get("page_number") is not None
    }

    return {
        "requirement_ids": requirement_ids,
        "section_ids": section_ids,
        "table_ids": table_ids,
        "figure_ids": figure_ids,
        "page_numbers": page_numbers,
    }


def get_test_id(vplan_item: dict[str, Any], fallback_index: int) -> str:
    return str(
        vplan_item.get("test_id")
        or vplan_item.get("id")
        or f"VPLAN_ITEM_{fallback_index + 1:03d}"
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


def collect_explicit_trace_values(vplan_item: dict[str, Any]) -> list[str]:
    trace_values = []

    for field in TRACEABILITY_FIELDS:
        value = vplan_item.get(field)

        if not value_has_content(value):
            continue

        if isinstance(value, list):
            trace_values.extend(str(item) for item in value if value_has_content(item))
        elif isinstance(value, dict):
            trace_values.extend(
                str(item) for item in value.values() if value_has_content(item)
            )
        else:
            trace_values.append(str(value))

    return trace_values


def collect_embedded_trace_values(vplan_item: dict[str, Any]) -> list[str]:
    searchable_text = json.dumps(vplan_item, ensure_ascii=False)

    matches = []

    matches.extend(REQUIREMENT_PATTERN.findall(searchable_text))
    matches.extend(SECTION_PATTERN.findall(searchable_text))

    table_matches = TABLE_PATTERN.findall(searchable_text)
    figure_matches = FIGURE_PATTERN.findall(searchable_text)

    matches.extend(table_matches)
    matches.extend(figure_matches)

    return [str(match) for match in matches if str(match).strip()]


def normalise_table_or_figure_reference(value: str) -> str:
    """
    Converts strings like 'Table A2.1' into 'A2.1' so they can be compared
    against extracted table IDs if needed.
    """

    value = value.strip()

    value = re.sub(r"^(table|figure)\s+", "", value, flags=re.IGNORECASE)

    return value.strip()


def trace_value_exists_in_spec(
    trace_value: str, spec_sources: dict[str, set[str]]
) -> bool:
    value = trace_value.strip()

    if not value:
        return False

    normalised_value = normalise_table_or_figure_reference(value)

    return (
        value in spec_sources["requirement_ids"]
        or value in spec_sources["section_ids"]
        or value in spec_sources["table_ids"]
        or value in spec_sources["figure_ids"]
        or value in spec_sources["page_numbers"]
        or normalised_value in spec_sources["section_ids"]
        or normalised_value in spec_sources["table_ids"]
        or normalised_value in spec_sources["figure_ids"]
    )


def vplan_item_has_source_in_spec(
    vplan_item: dict[str, Any],
    spec_sources: dict[str, set[str]],
) -> bool:
    trace_values = collect_explicit_trace_values(vplan_item)
    trace_values.extend(collect_embedded_trace_values(vplan_item))

    return any(
        trace_value_exists_in_spec(trace_value, spec_sources)
        for trace_value in trace_values
    )


def calculate_orphan_vplan_item_rate(
    spec_data: dict[str, Any],
    vplan_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Orphan vPlan Item Rate =
        number of vPlan items with no source in spec
        / total vPlan items
        * 100
    """

    total_vplan_items = len(vplan_items)
    spec_sources = extract_spec_sources(spec_data)

    linked_items = []
    orphan_items = []

    for index, item in enumerate(vplan_items):
        item_summary = {
            "vplan_index": index,
            "test_id": get_test_id(item, index),
            "requirement_id": item.get("requirement_id"),
            "source_section": item.get("source_section"),
            "test_description": item.get("test_description"),
        }

        if vplan_item_has_source_in_spec(item, spec_sources):
            linked_items.append(item_summary)
        else:
            orphan_items.append(item_summary)

    orphan_count = len(orphan_items)

    orphan_rate = (
        round((orphan_count / total_vplan_items) * 100, 2)
        if total_vplan_items > 0
        else 0.0
    )

    return {
        "metric_name": "Orphan vPlan Item Rate",
        "definition": "Percentage of vPlan items that do not trace back to any spec content.",
        "formula": "(vplan_items_with_no_source_in_spec / total_vplan_items) * 100",
        "total_vplan_items": total_vplan_items,
        "vplan_items_with_source_in_spec": len(linked_items),
        "orphan_vplan_items": orphan_count,
        "orphan_rate": orphan_rate,
        "linked_items": linked_items,
        "orphan_items": orphan_items,
    }


def run_orphan_vplan_item_rate(
    spec_file: str | Path,
    vplan_file: str | Path,
) -> dict[str, Any]:
    spec_data = load_json(spec_file)
    vplan_data = load_json(vplan_file)

    if not isinstance(spec_data, dict):
        raise ValueError("Spec file must contain a JSON object.")

    vplan_items = extract_vplan_items(vplan_data)

    return calculate_orphan_vplan_item_rate(
        spec_data=spec_data,
        vplan_items=vplan_items,
    )


def print_orphan_vplan_item_rate_summary(result: dict[str, Any]) -> None:
    print("\nOrphan vPlan Item Rate")
    print("----------------------")
    print(f"Total vPlan items:             {result['total_vplan_items']}")
    print(f"vPlan items with spec source:  {result['vplan_items_with_source_in_spec']}")
    print(f"Orphan vPlan items:            {result['orphan_vplan_items']}")
    print(f"Orphan rate:                   {result['orphan_rate']}%")

    if result["orphan_items"]:
        print("\nOrphan vPlan item IDs:")
        for item in result["orphan_items"]:
            print(f"  - {item['test_id']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate deterministic orphan vPlan item rate."
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

    result = run_orphan_vplan_item_rate(
        spec_file=args.spec_file,
        vplan_file=args.vplan_file,
    )

    print_orphan_vplan_item_rate_summary(result)
