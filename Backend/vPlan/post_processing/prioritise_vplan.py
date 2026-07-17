from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from Backend.config import MAX_PRIORITY_SELECTIONS

SELECTION_SEPARATOR = "::"


def normalise_category(category: str) -> str:
    return " ".join(category.strip().split()).casefold()


def priority_selection(test: dict) -> str:
    """Return the hierarchical selector, with legacy vPlans still supported."""

    parent = str(test.get("requirement_category", "")).strip()
    child = str(test.get("requirement_subcategory", "")).strip()

    if parent and parent.casefold() != "uncategorised" and child:
        return normalise_category(f"{parent}{SELECTION_SEPARATOR}{child}")

    return normalise_category(str(test.get("category", "")))


def prioritise_vplan(
    vplan_file: str | Path,
    priority_1_categories: list[str],
    priority_2_categories: list[str],
    output_dir: str | Path,
) -> Path:
    input_path = Path(vplan_file)
    output_directory = Path(output_dir)

    if not input_path.exists():
        raise ValueError(f"vPlan file does not exist: {input_path}")

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    with input_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        vplan_data = json.load(file)

    tests = vplan_data.get("feature_list")

    if not isinstance(tests, list):
        raise ValueError("The vPlan must contain a 'feature_list' array.")

    priority_one = {
        normalise_category(category)
        for category in priority_1_categories
        if category.strip()
    }

    priority_two = {
        normalise_category(category)
        for category in priority_2_categories
        if category.strip()
    }

    if not priority_one:
        raise ValueError("At least one Priority 1 category must be selected.")

    selected_category_count = len(priority_one | priority_two)

    if selected_category_count < 2:
        raise ValueError("Select at least two categories in total.")

    if selected_category_count > MAX_PRIORITY_SELECTIONS:
        raise ValueError(
            f"Select no more than {MAX_PRIORITY_SELECTIONS} categories or "
            "subcategories in total."
        )

    overlapping_categories = priority_one & priority_two

    if overlapping_categories:
        raise ValueError(
            "Categories cannot appear in both priority groups: "
            + ", ".join(sorted(overlapping_categories))
        )

    available_categories = {
        priority_selection(test) for test in tests if priority_selection(test)
    }

    requested_categories = priority_one | priority_two

    unknown_categories = requested_categories - available_categories

    if unknown_categories:
        raise ValueError(
            "Unknown vPlan categories: " + ", ".join(sorted(unknown_categories))
        )

    for test in tests:
        category = priority_selection(test)

        if category in priority_one:
            test["priority"] = 1
        elif category in priority_two:
            test["priority"] = 2
        else:
            test["priority"] = 3

    tests.sort(
        key=lambda test: (
            int(test.get("priority", 3)),
            str(test.get("test_id", "")),
        )
    )

    metadata = vplan_data.setdefault(
        "metadata",
        {},
    )

    metadata["prioritised"] = True
    metadata["priority_1_categories"] = priority_1_categories
    metadata["priority_2_categories"] = priority_2_categories
    metadata["prioritised_at"] = datetime.now().isoformat(timespec="seconds")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    output_path = output_directory / f"prioritised_vplan_{timestamp}.json"

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            vplan_data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_path
