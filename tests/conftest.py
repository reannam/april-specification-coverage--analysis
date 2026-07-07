import json
from pathlib import Path

import pytest


@pytest.fixture
def strong_requirements() -> list[dict]:
    return [
        {
            "id": "REQ_I2C_001",
            "description": "The I2C core must operate in normal mode.",
            "text": "The core shall operate at 100 Kbps.",
        },
        {
            "id": "REQ_I2C_002",
            "description": "SCL is required to be a single-bit signal.",
            "text": "SCL requires a width of 1 bit.",
        },
    ]


@pytest.fixture
def weak_requirements() -> list[dict]:
    return [
        {
            "id": "REQ_I2C_003",
            "description": "The controller should support fast-mode operation.",
            "text": "Fast-mode operation may be available where supported.",
        },
        {
            "id": "REQ_I2C_004",
            "description": "The interrupt output can be asserted as appropriate.",
            "text": "The interrupt behaviour is implementation-defined.",
        },
    ]


@pytest.fixture
def mixed_requirements(
    strong_requirements: list[dict],
    weak_requirements: list[dict],
) -> list[dict]:
    return strong_requirements + weak_requirements


@pytest.fixture
def requirements_wrapped_dict(mixed_requirements: list[dict]) -> dict:
    return {
        "requirements": mixed_requirements,
    }


@pytest.fixture
def extracted_requirements_file(
    tmp_path: Path,
    mixed_requirements: list[dict],
) -> Path:
    file_path = tmp_path / "example-requirements.json"
    file_path.write_text(
        json.dumps(mixed_requirements, indent=2),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def wrapped_requirements_file(
    tmp_path: Path,
    requirements_wrapped_dict: dict,
) -> Path:
    file_path = tmp_path / "wrapped-requirements.json"
    file_path.write_text(
        json.dumps(requirements_wrapped_dict, indent=2),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def malformed_json_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "malformed.json"
    file_path.write_text("{ this is not valid json", encoding="utf-8")
    return file_path


@pytest.fixture
def empty_json_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "empty.json"
    file_path.write_text("", encoding="utf-8")
    return file_path