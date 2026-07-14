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


@pytest.fixture
def write_json():
    def _write(path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def sample_spec():
    return {
        "requirements": [
            {
                "id": "REQ_A2_1_001",
                "text": "The controller shall transfer data.",
                "source_section": "A2.1",
                "type": "protocol_rule",
            },
            {
                "id": "REQ_A2_1_002",
                "text": "The controller may support an optional mode.",
                "source_section": "A2.1",
            },
            {
                "id": "REQ_A2_1_003",
                "text": "The receiver shall reject invalid data.",
                "source_section": "A2.1",
            },
        ],
        "sections": [{"id": "A2.1"}],
        "tables": [{"id": "A2.1"}],
        "figures": [{"id": "A2.2"}],
        "pages": [{"page_number": 12}],
    }


@pytest.fixture
def sample_vplan():
    return {
        "feature_list": [
            {
                "test_id": "TEST_001",
                "requirement_id": "REQ_A2_1_001",
                "source_section": "A2.1",
                "test_description": "Verify data transfer.",
                "test_steps": ["Drive valid data."],
                "expected_results": ["Data is transferred."],
                "coverage": "covered",
            },
            {
                "test_id": "TEST_002",
                "requirement_id": "REQ_A2_1_002",
                "test_description": "Verify optional mode when enabled.",
                "test_steps": ["Enable the mode."],
                "expected_results": ["The mode operates."],
                "coverage": "partially_covered",
            },
        ]
    }


@pytest.fixture
def sample_labelled_requirements():
    return [
        {
            "id": "REQ_A2_1_001",
            "text": "The controller shall transfer data.",
            "source_section": "A2.1",
            "verified_coverage_status": "Covered",
            "coverage_verification_reason": "A covered test exists.",
            "linked_tests": ["TEST_001"],
            "original_vplan_coverage_values": ["covered"],
            "linked_edge_cases": [],
            "linked_weak_word_flags": [],
        },
        {
            "id": "REQ_A2_1_002",
            "text": "The controller may support an optional mode.",
            "source_section": "A2.1",
            "verified_coverage_status": "Partially covered",
            "coverage_verification_reason": "Optional language remains.",
            "linked_tests": ["TEST_002"],
            "original_vplan_coverage_values": ["partially_covered"],
            "linked_edge_cases": [],
            "linked_weak_word_flags": [{"matched_words": ["may"]}],
        },
        {
            "id": "REQ_A2_1_003",
            "text": "The receiver shall reject invalid data.",
            "source_section": "A2.1",
            "verified_coverage_status": "Ambiguous / not yet plannable",
            "coverage_verification_reason": "A blocked test has ambiguity evidence.",
            "linked_tests": ["TEST_003"],
            "original_vplan_coverage_values": ["blocked"],
            "linked_edge_cases": [{"edge_case_id": "EDGE_001"}],
            "linked_weak_word_flags": [],
        },
    ]
