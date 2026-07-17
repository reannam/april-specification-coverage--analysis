# Backend/preprocess_requirements.py

import json
from pathlib import Path

from Backend.config import PREPROCESSED_REQUIREMENTS_DIR


def preprocess_requirements_file(
    requirements_file: str | Path,
    output_dir: str | Path = PREPROCESSED_REQUIREMENTS_DIR,
) -> Path:
    """
    Takes a full document JSON file and extracts only the top-level
    'requirements' section into a new JSON file.

    Returns the path to the preprocessed requirements-only file.
    """

    input_path = Path(requirements_file)

    if not input_path.exists():
        raise FileNotFoundError(f"Requirements file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if "requirements" not in data:
        raise KeyError(
            f"No 'requirements' section found in {input_path}. "
            "Expected full document JSON with a top-level 'requirements' key."
        )

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    output_path = destination / f"{input_path.stem}_requirements_only.json"

    cleaned_data = {"requirements": data["requirements"]}

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

    return output_path
