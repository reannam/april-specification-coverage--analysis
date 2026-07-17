"""Create the compact requirements input consumed by the vPlan workflow."""

import json
from pathlib import Path
import re

from Backend.config import EXTRACTION_OUTPUT_DIR
from Backend.Extraction.regex_patterns import (
    DECLARATIVE_BEHAVIOUR_REGEX,
    FEATURE_REGEX,
    REQUIREMENT_REGEX,
)


def is_vplan_relevant(text: str) -> bool:
    """Keep normative behavior while excluding illustrative figure prose."""

    normalised = " ".join(text.split()).strip()
    if not normalised:
        return False
    if re.search(
        r"\b(?:Figure|Fig\.?)\s+[A-Za-z]?\d+(?:\.\d+)*",
        normalised,
        re.IGNORECASE,
    ):
        return False
    if re.match(
        r"^(?:In Figure|As shown in Figure|The figure shows|"
        r"This assertion indicates|In this case|For example)\b",
        normalised,
        re.IGNORECASE,
    ):
        return False
    return bool(
        REQUIREMENT_REGEX.search(normalised)
        or DECLARATIVE_BEHAVIOUR_REGEX.search(normalised)
        or FEATURE_REGEX.search(normalised)
    )


def write_requirements_file(
    extracted_document_path: str | Path,
    *,
    output_dir: str | Path = EXTRACTION_OUTPUT_DIR,
) -> dict:
    """Validate an extracted document and persist its requirements-only view."""

    source_path = Path(extracted_document_path)
    with source_path.open("r", encoding="utf-8") as source_file:
        document = json.load(source_file)

    if not isinstance(document, dict):
        raise ValueError("Extracted JSON must contain an object at the top level.")

    requirements = document.get("requirements")
    if not isinstance(requirements, list):
        raise ValueError(
            "Extracted JSON must contain a top-level 'requirements' array."
        )

    invalid_indexes = [
        index
        for index, requirement in enumerate(requirements)
        if not isinstance(requirement, dict)
        or not str(requirement.get("text", "")).strip()
    ]
    if invalid_indexes:
        preview = ", ".join(str(index) for index in invalid_indexes[:10])
        raise ValueError(
            "Every requirement must be an object with non-empty text. "
            f"Invalid array indexes: {preview}."
        )

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / f"{source_path.stem}_requirements.json"
    relevant_requirements = [
        requirement
        for requirement in requirements
        if is_vplan_relevant(str(requirement["text"]))
    ]
    output = {
        "document_name": document.get("document_name") or source_path.name,
        "refinement_summary": {
            "input_requirements": len(requirements),
            "vplan_relevant_requirements": len(relevant_requirements),
            "excluded_requirements": len(requirements) - len(relevant_requirements),
        },
        "requirements": relevant_requirements,
    }

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(output, output_file, indent=2, ensure_ascii=False)

    return {
        "document": output,
        "output_path": output_path,
    }
