import json

import pytest

from pathlib import Path

from Backend.report_generation import vplan_traceability_check as trace


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
def valid_vplan_file(tmp_path, valid_vplan_data) -> Path:
    file_path = tmp_path / "generated-vplan.json"
    file_path.write_text(
        json.dumps(valid_vplan_data, indent=2),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def vplan_with_missing_requirement_file(tmp_path) -> Path:
    file_path = tmp_path / "vplan-missing-requirements.json"
    file_path.write_text(
        json.dumps(
            {
                "feature_list": [
                    {
                        "test_id": "TEST_REQ_I2C_001_001",
                        "requirement_id": "REQ_I2C_001",
                    },
                    {
                        "test_id": "TEST_REQ_I2C_002_001",
                        "requirement_id": "REQ_I2C_002",
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def vplan_with_extra_requirement_file(tmp_path) -> Path:
    file_path = tmp_path / "vplan-extra-requirements.json"
    file_path.write_text(
        json.dumps(
            {
                "feature_list": [
                    {
                        "test_id": "TEST_REQ_I2C_001_001",
                        "requirement_id": "REQ_I2C_001",
                    },
                    {
                        "test_id": "TEST_UNKNOWN_001",
                        "requirement_id": "REQ_DOES_NOT_EXIST",
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def vplan_with_duplicate_test_ids_file(tmp_path) -> Path:
    file_path = tmp_path / "vplan-duplicate-test-ids.json"
    file_path.write_text(
        json.dumps(
            {
                "feature_list": [
                    {
                        "test_id": "TEST_DUPLICATE_001",
                        "requirement_id": "REQ_I2C_001",
                    },
                    {
                        "test_id": "TEST_DUPLICATE_001",
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
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def vplan_with_multiple_tests_per_requirement_file(tmp_path) -> Path:
    file_path = tmp_path / "vplan-multiple-tests.json"
    file_path.write_text(
        json.dumps(
            {
                "feature_list": [
                    {
                        "test_id": "TEST_REQ_I2C_001_001",
                        "requirement_id": "REQ_I2C_001",
                    },
                    {
                        "test_id": "TEST_REQ_I2C_001_002",
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
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def vplan_with_missing_row_ids_file(tmp_path) -> Path:
    file_path = tmp_path / "vplan-missing-row-ids.json"
    file_path.write_text(
        json.dumps(
            {
                "feature_list": [
                    {
                        "test_id": "TEST_REQ_I2C_001_001",
                        "requirement_id": "REQ_I2C_001",
                    },
                    {
                        "test_id": "TEST_MISSING_REQ_ID",
                    },
                    {
                        "not_a_test": True,
                    },
                    "bad row",
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def requirements_with_missing_ids_file(tmp_path) -> Path:
    file_path = tmp_path / "requirements-missing-ids.json"
    file_path.write_text(
        json.dumps(
            [
                {
                    "id": "REQ_I2C_001",
                    "description": "The controller must operate in normal mode.",
                    "text": "The controller shall operate at 100 Kbps.",
                },
                {
                    "description": "This requirement has no ID.",
                    "text": "The signal shall reset.",
                },
                "bad requirement",
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    return file_path


# ---------------------------------------------------------------------------
# check_traceability: passing case
# ---------------------------------------------------------------------------


def test_check_traceability_passes_for_valid_traceability(
    extracted_requirements_file,
    valid_vplan_file,
    capsys,
):
    result = trace.check_traceability(
        str(extracted_requirements_file),
        str(valid_vplan_file),
    )

    captured = capsys.readouterr()

    assert result is None
    assert "Traceability sanity check" in captured.out
    assert "Input requirements: 4" in captured.out
    assert "Output vPlan rows/tests: 4" in captured.out
    assert "Output vPlan requirement IDs: 4" in captured.out
    assert "No missing requirement IDs." in captured.out
    assert "No unexpected requirement IDs." in captured.out
    assert "No duplicate test IDs." in captured.out
    assert "No requirement IDs have multiple tests." in captured.out
    assert "Traceability check passed." in captured.out


def test_check_traceability_accepts_wrapped_requirements_file(
    wrapped_requirements_file,
    valid_vplan_file,
    capsys,
):
    trace.check_traceability(
        str(wrapped_requirements_file),
        str(valid_vplan_file),
    )

    captured = capsys.readouterr()

    assert "Input requirements: 4" in captured.out
    assert "Traceability check passed." in captured.out


# ---------------------------------------------------------------------------
# check_traceability: missing / extra IDs
# ---------------------------------------------------------------------------


def test_check_traceability_reports_missing_requirement_ids(
    extracted_requirements_file,
    vplan_with_missing_requirement_file,
    capsys,
):
    trace.check_traceability(
        str(extracted_requirements_file),
        str(vplan_with_missing_requirement_file),
    )

    captured = capsys.readouterr()

    assert "Missing requirement IDs:" in captured.out
    assert "- REQ_I2C_003" in captured.out
    assert "- REQ_I2C_004" in captured.out
    assert "No unexpected requirement IDs." in captured.out
    assert "Traceability check failed." in captured.out


def test_check_traceability_reports_unexpected_requirement_ids(
    extracted_requirements_file,
    vplan_with_extra_requirement_file,
    capsys,
):
    trace.check_traceability(
        str(extracted_requirements_file),
        str(vplan_with_extra_requirement_file),
    )

    captured = capsys.readouterr()

    assert "Unexpected requirement IDs:" in captured.out
    assert "- REQ_DOES_NOT_EXIST" in captured.out
    assert "Traceability check failed." in captured.out


def test_check_traceability_reports_missing_and_extra_requirement_ids(
    tmp_path,
    extracted_requirements_file,
    capsys,
):
    data = {
        "feature_list": [
            {
                "test_id": "TEST_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
            },
            {
                "test_id": "TEST_UNKNOWN_001",
                "requirement_id": "REQ_UNKNOWN",
            },
        ]
    }

    vplan_file = tmp_path / "vplan-missing-and-extra.json"
    vplan_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    trace.check_traceability(
        str(extracted_requirements_file),
        str(vplan_file),
    )

    captured = capsys.readouterr()

    assert "Missing requirement IDs:" in captured.out
    assert "- REQ_I2C_002" in captured.out
    assert "- REQ_I2C_003" in captured.out
    assert "- REQ_I2C_004" in captured.out
    assert "Unexpected requirement IDs:" in captured.out
    assert "- REQ_UNKNOWN" in captured.out
    assert "Traceability check failed." in captured.out


# ---------------------------------------------------------------------------
# check_traceability: duplicate test IDs
# ---------------------------------------------------------------------------


def test_check_traceability_reports_duplicate_test_ids(
    extracted_requirements_file,
    vplan_with_duplicate_test_ids_file,
    capsys,
):
    trace.check_traceability(
        str(extracted_requirements_file),
        str(vplan_with_duplicate_test_ids_file),
    )

    captured = capsys.readouterr()

    assert "Duplicate test IDs:" in captured.out
    assert "- TEST_DUPLICATE_001: appears 2 times" in captured.out
    assert "Traceability check failed." in captured.out


def test_check_traceability_passes_when_only_multiple_tests_exist(
    extracted_requirements_file,
    vplan_with_multiple_tests_per_requirement_file,
    capsys,
):
    """
    Multiple tests per requirement are reported, but they are not treated as
    a traceability failure by the current implementation.
    """
    trace.check_traceability(
        str(extracted_requirements_file),
        str(vplan_with_multiple_tests_per_requirement_file),
    )

    captured = capsys.readouterr()

    assert "Requirement IDs with multiple atomic tests:" in captured.out
    assert "- REQ_I2C_001: has 2 tests" in captured.out
    assert "Traceability check passed." in captured.out


# ---------------------------------------------------------------------------
# check_traceability: missing IDs in input or output rows
# ---------------------------------------------------------------------------


def test_check_traceability_reports_input_requirements_missing_ids(
    requirements_with_missing_ids_file,
    tmp_path,
    capsys,
):
    vplan_data = {
        "feature_list": [
            {
                "test_id": "TEST_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
            }
        ]
    }

    vplan_file = tmp_path / "vplan-valid-for-one-id.json"
    vplan_file.write_text(json.dumps(vplan_data, indent=2), encoding="utf-8")

    trace.check_traceability(
        str(requirements_with_missing_ids_file),
        str(vplan_file),
    )

    captured = capsys.readouterr()

    assert "Input requirements: 1" in captured.out
    assert "Warning: 2 input requirements are missing IDs." in captured.out
    assert "Traceability check passed." in captured.out


def test_check_traceability_reports_vplan_rows_missing_requirement_ids(
    extracted_requirements_file,
    vplan_with_missing_row_ids_file,
    capsys,
):
    trace.check_traceability(
        str(extracted_requirements_file),
        str(vplan_with_missing_row_ids_file),
    )

    captured = capsys.readouterr()

    assert "Warning: 3 vPlan rows are missing requirement IDs." in captured.out
    assert "Missing requirement IDs:" in captured.out
    assert "- REQ_I2C_002" in captured.out
    assert "- REQ_I2C_003" in captured.out
    assert "- REQ_I2C_004" in captured.out
    assert "Traceability check failed." in captured.out


def test_check_traceability_handles_empty_feature_list(
    extracted_requirements_file,
    tmp_path,
    capsys,
):
    vplan_file = tmp_path / "empty-vplan.json"
    vplan_file.write_text(json.dumps({"feature_list": []}), encoding="utf-8")

    trace.check_traceability(
        str(extracted_requirements_file),
        str(vplan_file),
    )

    captured = capsys.readouterr()

    assert "Output vPlan rows/tests: 0" in captured.out
    assert "Output vPlan requirement IDs: 0" in captured.out
    assert "Missing requirement IDs:" in captured.out
    assert "- REQ_I2C_001" in captured.out
    assert "- REQ_I2C_002" in captured.out
    assert "- REQ_I2C_003" in captured.out
    assert "- REQ_I2C_004" in captured.out
    assert "Traceability check failed." in captured.out


def test_check_traceability_handles_missing_feature_list_key(
    extracted_requirements_file,
    tmp_path,
    capsys,
):
    vplan_file = tmp_path / "missing-feature-list.json"
    vplan_file.write_text(
        json.dumps({"metadata": {"name": "No rows"}}), encoding="utf-8"
    )

    trace.check_traceability(
        str(extracted_requirements_file),
        str(vplan_file),
    )

    captured = capsys.readouterr()

    assert "Output vPlan rows/tests: 0" in captured.out
    assert "Missing requirement IDs:" in captured.out
    assert "Traceability check failed." in captured.out


def test_check_traceability_ignores_non_dict_vplan_rows(
    extracted_requirements_file,
    tmp_path,
    capsys,
):
    data = {
        "feature_list": [
            {
                "test_id": "TEST_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
            },
            "bad row",
            123,
            None,
        ]
    }

    vplan_file = tmp_path / "vplan-non-dict-rows.json"
    vplan_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    trace.check_traceability(
        str(extracted_requirements_file),
        str(vplan_file),
    )

    captured = capsys.readouterr()

    assert "Output vPlan rows/tests: 4" in captured.out
    assert "Warning: 3 vPlan rows are missing requirement IDs." in captured.out
    assert "Missing requirement IDs:" in captured.out
    assert "Traceability check failed." in captured.out


# ---------------------------------------------------------------------------
# check_traceability: file / JSON errors
# ---------------------------------------------------------------------------


def test_check_traceability_raises_for_missing_requirements_file(
    tmp_path,
    valid_vplan_file,
):
    missing_requirements_file = tmp_path / "missing-requirements.json"

    with pytest.raises(FileNotFoundError):
        trace.check_traceability(
            str(missing_requirements_file),
            str(valid_vplan_file),
        )


def test_check_traceability_raises_for_missing_vplan_file(
    extracted_requirements_file,
    tmp_path,
):
    missing_vplan_file = tmp_path / "missing-vplan.json"

    with pytest.raises(FileNotFoundError):
        trace.check_traceability(
            str(extracted_requirements_file),
            str(missing_vplan_file),
        )


def test_check_traceability_raises_for_malformed_requirements_json(
    malformed_json_file,
    valid_vplan_file,
):
    with pytest.raises(json.JSONDecodeError):
        trace.check_traceability(
            str(malformed_json_file),
            str(valid_vplan_file),
        )


def test_check_traceability_raises_for_malformed_vplan_json(
    extracted_requirements_file,
    malformed_json_file,
):
    with pytest.raises(json.JSONDecodeError):
        trace.check_traceability(
            str(extracted_requirements_file),
            str(malformed_json_file),
        )


def test_check_traceability_raises_for_invalid_requirements_shape(
    tmp_path,
    valid_vplan_file,
):
    requirements_file = tmp_path / "invalid-requirements.json"
    requirements_file.write_text(
        json.dumps({"requirements": "not a list"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Expected requirements to be a list"):
        trace.check_traceability(
            str(requirements_file),
            str(valid_vplan_file),
        )


def test_check_traceability_raises_when_vplan_json_is_list(
    extracted_requirements_file,
    tmp_path,
):
    """
    Current behaviour: generated_vplan is expected to be a dict because the
    function calls generated_vplan.get("feature_list", []).
    """
    vplan_file = tmp_path / "vplan-list.json"
    vplan_file.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(AttributeError):
        trace.check_traceability(
            str(extracted_requirements_file),
            str(vplan_file),
        )


# ---------------------------------------------------------------------------
# add_requirement_text
# ---------------------------------------------------------------------------


def test_add_requirement_text_adds_text_to_each_vplan_row(
    valid_vplan_data,
    mixed_requirements,
):
    result = trace.add_requirement_text(valid_vplan_data, mixed_requirements)

    rows = result["feature_list"]

    assert rows[0]["requirement_text"] == "The core shall operate at 100 Kbps."
    assert rows[1]["requirement_text"] == "SCL requires a width of 1 bit."
    assert (
        rows[2]["requirement_text"]
        == "Fast-mode operation may be available where supported."
    )
    assert (
        rows[3]["requirement_text"]
        == "The interrupt behaviour is implementation-defined."
    )


def test_add_requirement_text_accepts_wrapped_requirements_dict(
    valid_vplan_data,
    requirements_wrapped_dict,
):
    result = trace.add_requirement_text(valid_vplan_data, requirements_wrapped_dict)

    rows = result["feature_list"]

    assert rows[0]["requirement_text"] == "The core shall operate at 100 Kbps."
    assert rows[1]["requirement_text"] == "SCL requires a width of 1 bit."


def test_add_requirement_text_sets_empty_string_for_unknown_requirement_id(
    mixed_requirements,
):
    vplan_data = {
        "feature_list": [
            {
                "test_id": "TEST_UNKNOWN_001",
                "requirement_id": "REQ_UNKNOWN",
            }
        ]
    }

    result = trace.add_requirement_text(vplan_data, mixed_requirements)

    assert result["feature_list"][0]["requirement_text"] == ""


def test_add_requirement_text_sets_empty_string_for_missing_requirement_id(
    mixed_requirements,
):
    vplan_data = {
        "feature_list": [
            {
                "test_id": "TEST_MISSING_REQ_ID",
            }
        ]
    }

    result = trace.add_requirement_text(vplan_data, mixed_requirements)

    assert result["feature_list"][0]["requirement_text"] == ""


def test_add_requirement_text_skips_non_dict_rows(mixed_requirements):
    vplan_data = {
        "feature_list": [
            {
                "test_id": "TEST_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
            },
            "bad row",
            123,
            None,
        ]
    }

    result = trace.add_requirement_text(vplan_data, mixed_requirements)

    assert (
        result["feature_list"][0]["requirement_text"]
        == "The core shall operate at 100 Kbps."
    )
    assert result["feature_list"][1] == "bad row"
    assert result["feature_list"][2] == 123
    assert result["feature_list"][3] is None


def test_add_requirement_text_handles_missing_feature_list_key(mixed_requirements):
    vplan_data = {"metadata": {"name": "No feature list"}}

    result = trace.add_requirement_text(vplan_data, mixed_requirements)

    assert result == {"metadata": {"name": "No feature list"}}


def test_add_requirement_text_returns_same_dict_object(
    valid_vplan_data,
    mixed_requirements,
):
    result = trace.add_requirement_text(valid_vplan_data, mixed_requirements)

    assert result is valid_vplan_data


def test_add_requirement_text_ignores_requirements_without_ids(valid_vplan_data):
    requirements = [
        {
            "id": "REQ_I2C_001",
            "text": "Requirement text for REQ_I2C_001.",
        },
        {
            "text": "No ID requirement.",
        },
        "bad requirement",
    ]

    result = trace.add_requirement_text(valid_vplan_data, requirements)

    assert (
        result["feature_list"][0]["requirement_text"]
        == "Requirement text for REQ_I2C_001."
    )
    assert result["feature_list"][1]["requirement_text"] == ""
    assert result["feature_list"][2]["requirement_text"] == ""
    assert result["feature_list"][3]["requirement_text"] == ""


def test_add_requirement_text_uses_empty_string_when_requirement_has_no_text():
    requirements = [
        {
            "id": "REQ_I2C_001",
        }
    ]

    vplan_data = {
        "feature_list": [
            {
                "test_id": "TEST_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
            }
        ]
    }

    result = trace.add_requirement_text(vplan_data, requirements)

    assert result["feature_list"][0]["requirement_text"] == ""


def test_add_requirement_text_raises_for_invalid_requirements_shape(valid_vplan_data):
    requirements = {"requirements": "not a list"}

    with pytest.raises(ValueError, match="Expected requirements to be a list"):
        trace.add_requirement_text(valid_vplan_data, requirements)
