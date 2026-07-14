from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def first_string(
    *values: Any,
) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def clean_filename_title(
    filename: str,
) -> str:
    name = Path(filename).stem

    # Remove the UUID added when the API stores an upload.
    name = re.sub(
        r"^[a-f0-9]{32}_",
        "",
        name,
        flags=re.IGNORECASE,
    )

    name = re.sub(
        r"_requirements_only$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    name = re.sub(
        r"_extracted_chapter(?:\(\d+\))?$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip()

    return name.title() or "Specification"


def get_requirement_items(
    requirements_data: Any,
) -> list[dict]:
    if isinstance(requirements_data, list):
        return [item for item in requirements_data if isinstance(item, dict)]

    if not isinstance(requirements_data, dict):
        return []

    for key in (
        "requirements",
        "items",
        "spec_items",
        "feature_list",
    ):
        value = requirements_data.get(key)

        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    return []


def determine_section(
    requirements_data: Any,
) -> str | None:
    if isinstance(requirements_data, dict):
        metadata = requirements_data.get("metadata", {})

        if not isinstance(metadata, dict):
            metadata = {}

        explicit_section = first_string(
            metadata.get("section"),
            metadata.get("source_section"),
            metadata.get("chapter"),
            requirements_data.get("section"),
            requirements_data.get("source_section"),
            requirements_data.get("chapter"),
        )

        if explicit_section:
            return explicit_section

    requirements = get_requirement_items(requirements_data)

    sections = {
        str(
            requirement.get("source_section")
            or requirement.get("section")
            or requirement.get("section_id")
            or ""
        ).strip()
        for requirement in requirements
    }

    sections.discard("")

    if len(sections) == 1:
        return next(iter(sections))

    return None


def build_vplan_metadata(
    *,
    requirements_file: str | Path,
    existing_metadata: dict | None = None,
) -> dict:
    requirements_path = Path(requirements_file).resolve()

    with requirements_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        requirements_data = json.load(file)

    requirements_metadata = {}

    if isinstance(requirements_data, dict):
        possible_metadata = requirements_data.get(
            "metadata",
            {},
        )

        if isinstance(possible_metadata, dict):
            requirements_metadata = possible_metadata

    specification_name = first_string(
        requirements_metadata.get("specification_name"),
        requirements_metadata.get("document_title"),
        requirements_metadata.get("title"),
        (
            requirements_data.get("specification_name")
            if isinstance(
                requirements_data,
                dict,
            )
            else None
        ),
        (
            requirements_data.get("title")
            if isinstance(
                requirements_data,
                dict,
            )
            else None
        ),
    )

    if not specification_name:
        specification_name = clean_filename_title(requirements_path.name)

    section = determine_section(requirements_data)

    if section:
        display_name = f"{specification_name} " f"Section {section} Verification Plan"
    else:
        display_name = f"{specification_name} " "Verification Plan"

    metadata = dict(existing_metadata or {})

    metadata.update(
        {
            "specification_name": specification_name,
            "section": section,
            "display_name": display_name,
            "requirements_file": requirements_path.name,
            "requirements_file_path": str(requirements_path),
        }
    )

    return metadata
