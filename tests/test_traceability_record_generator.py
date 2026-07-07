import csv
import json
from pathlib import Path

import pytest

from Backend.report_generation import traceability_record_generator as links


@pytest.fixture
def valid_vplan_data() -> dict:
    return {
        "feature_list": [
            {
                "test_id": "TEST_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
            },
            {
                "test_id": "TEST_REQ_I2C_002_001",
                "requirement_id": "REQ_I2C_002",
            },
            {
                "test_id": "TEST_REQ_I2C_003_001",
                "requirement_id": "REQ_I2C_003",
            },
            {
                "test_id": "TEST_REQ_I2C_004_001",
                "requirement_id": "REQ_I2C_004",
            },
        ]
    }


@pytest.fixture
def valid_vplan_file(tmp_path: Path, valid_vplan_data: dict) -> Path:
    file_path = tmp_path / "generated-vplan.json"
    file_path.write_text(
        json.dumps(valid_vplan_data, indent=2),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def nested_vplan_file(tmp_path: Path, valid_vplan_data: dict) -> Path:
    file_path = tmp_path / "nested-vplan.json"
    file_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "name": "Nested vPlan example",
                },
                "vplan": valid_vplan_data,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def vplan_missing_feature_list_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "missing-feature-list.json"
    file_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "name": "Invalid vPlan",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return file_path


# ---------------------------------------------------------------------------
# load_vplan
# ---------------------------------------------------------------------------


def test_load_vplan_loads_valid_json(valid_vplan_file):
    result = links.load_vplan(valid_vplan_file)

    assert isinstance(result, dict)
    assert "feature_list" in result


def test_load_vplan_raises_for_missing_file(tmp_path):
    missing_file = tmp_path / "missing-vplan.json"

    with pytest.raises(FileNotFoundError, match="vPlan file not found"):
        links.load_vplan(missing_file)


def test_load_vplan_raises_for_malformed_json(malformed_json_file):
    with pytest.raises(json.JSONDecodeError):
        links.load_vplan(malformed_json_file)


# ---------------------------------------------------------------------------
# get_vplan_rows
# ---------------------------------------------------------------------------


def test_get_vplan_rows_from_top_level_feature_list(valid_vplan_data):
    result = links.get_vplan_rows(valid_vplan_data)

    assert result == valid_vplan_data["feature_list"]


def test_get_vplan_rows_from_nested_vplan(valid_vplan_data):
    data = {"vplan": valid_vplan_data}

    result = links.get_vplan_rows(data)

    assert result == valid_vplan_data["feature_list"]


def test_get_vplan_rows_raises_when_feature_list_missing():
    data = {"metadata": {"name": "No feature list"}}

    with pytest.raises(ValueError, match="Could not find feature_list"):
        links.get_vplan_rows(data)


def test_get_vplan_rows_raises_when_nested_vplan_has_no_feature_list():
    data = {"vplan": {"metadata": {"name": "Bad nested vPlan"}}}

    with pytest.raises(ValueError, match="Could not find feature_list"):
        links.get_vplan_rows(data)


# ---------------------------------------------------------------------------
# build_requirement_test_map
# ---------------------------------------------------------------------------


def test_build_requirement_test_map_maps_requirements_to_tests():
    rows = [
        {
            "requirement_id": "REQ_I2C_001",
            "test_id": "TEST_REQ_I2C_001_001",
        },
        {
            "requirement_id": "REQ_I2C_002",
            "test_id": "TEST_REQ_I2C_002_001",
        },
    ]

    result = links.build_requirement_test_map(rows)

    assert result == {
        "REQ_I2C_001": ["TEST_REQ_I2C_001_001"],
        "REQ_I2C_002": ["TEST_REQ_I2C_002_001"],
    }


def test_build_requirement_test_map_groups_multiple_tests_per_requirement():
    rows = [
        {
            "requirement_id": "REQ_I2C_001",
            "test_id": "TEST_REQ_I2C_001_001",
        },
        {
            "requirement_id": "REQ_I2C_001",
            "test_id": "TEST_REQ_I2C_001_002",
        },
        {
            "requirement_id": "REQ_I2C_002",
            "test_id": "TEST_REQ_I2C_002_001",
        },
    ]

    result = links.build_requirement_test_map(rows)

    assert result == {
        "REQ_I2C_001": [
            "TEST_REQ_I2C_001_001",
            "TEST_REQ_I2C_001_002",
        ],
        "REQ_I2C_002": ["TEST_REQ_I2C_002_001"],
    }


def test_build_requirement_test_map_skips_rows_missing_requirement_id_or_test_id():
    rows = [
        {
            "requirement_id": "REQ_I2C_001",
            "test_id": "TEST_REQ_I2C_001_001",
        },
        {
            "requirement_id": "REQ_I2C_002",
        },
        {
            "test_id": "TEST_MISSING_REQUIREMENT",
        },
        {
            "requirement_id": "",
            "test_id": "TEST_EMPTY_REQUIREMENT",
        },
        {
            "requirement_id": "REQ_EMPTY_TEST",
            "test_id": "",
        },
    ]

    result = links.build_requirement_test_map(rows)

    assert result == {
        "REQ_I2C_001": ["TEST_REQ_I2C_001_001"],
    }


def test_build_requirement_test_map_returns_empty_dict_for_empty_rows():
    result = links.build_requirement_test_map([])

    assert result == {}


# ---------------------------------------------------------------------------
# export_requirement_test_links
# ---------------------------------------------------------------------------


def test_export_requirement_test_links_creates_csv(valid_vplan_file):
    csv_file = links.export_requirement_test_links(valid_vplan_file)

    assert csv_file.exists()
    assert csv_file.name == "generated-vplan_requirement_test_links.csv"

    with csv_file.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert reader.fieldnames == ["requirement_id", "related_tests"]
    assert len(rows) == 4

    first_row = rows[0]

    assert first_row["requirement_id"] == "REQ_I2C_001"
    assert json.loads(first_row["related_tests"]) == {
        "test_ids": ["TEST_REQ_I2C_001_001"]
    }

    csv_file.unlink()


def test_export_requirement_test_links_handles_nested_vplan(nested_vplan_file):
    csv_file = links.export_requirement_test_links(nested_vplan_file)

    assert csv_file.exists()
    assert csv_file.name == "nested-vplan_requirement_test_links.csv"

    with csv_file.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert len(rows) == 4
    assert rows[0]["requirement_id"] == "REQ_I2C_001"

    csv_file.unlink()


def test_export_requirement_test_links_groups_multiple_tests(tmp_path):
    data = {
        "feature_list": [
            {
                "requirement_id": "REQ_I2C_001",
                "test_id": "TEST_REQ_I2C_001_001",
            },
            {
                "requirement_id": "REQ_I2C_001",
                "test_id": "TEST_REQ_I2C_001_002",
            },
        ]
    }

    vplan_file = tmp_path / "multi-test-vplan.json"
    vplan_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    csv_file = links.export_requirement_test_links(vplan_file)

    with csv_file.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["requirement_id"] == "REQ_I2C_001"
    assert json.loads(rows[0]["related_tests"]) == {
        "test_ids": [
            "TEST_REQ_I2C_001_001",
            "TEST_REQ_I2C_001_002",
        ]
    }

    csv_file.unlink()


def test_export_requirement_test_links_skips_invalid_rows(tmp_path):
    data = {
        "feature_list": [
            {
                "requirement_id": "REQ_I2C_001",
                "test_id": "TEST_REQ_I2C_001_001",
            },
            {
                "requirement_id": "REQ_I2C_002",
            },
            {
                "test_id": "TEST_MISSING_REQUIREMENT",
            },
        ]
    }

    vplan_file = tmp_path / "invalid-rows-vplan.json"
    vplan_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    csv_file = links.export_requirement_test_links(vplan_file)

    with csv_file.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["requirement_id"] == "REQ_I2C_001"

    csv_file.unlink()


def test_export_requirement_test_links_creates_header_only_csv_for_empty_feature_list(
    tmp_path,
):
    data = {"feature_list": []}

    vplan_file = tmp_path / "empty-vplan.json"
    vplan_file.write_text(json.dumps(data), encoding="utf-8")

    csv_file = links.export_requirement_test_links(vplan_file)

    with csv_file.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert reader.fieldnames == ["requirement_id", "related_tests"]
    assert rows == []

    csv_file.unlink()


def test_export_requirement_test_links_raises_when_feature_list_missing(
    vplan_missing_feature_list_file,
):
    with pytest.raises(ValueError, match="Could not find feature_list"):
        links.export_requirement_test_links(vplan_missing_feature_list_file)


def test_export_requirement_test_links_raises_for_missing_vplan_file(tmp_path):
    missing_file = tmp_path / "missing-vplan.json"

    with pytest.raises(FileNotFoundError, match="vPlan file not found"):
        links.export_requirement_test_links(missing_file)
