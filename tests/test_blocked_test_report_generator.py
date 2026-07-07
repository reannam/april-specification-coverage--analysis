import json
from pathlib import Path

import pytest

from Backend.report_generation import blocked_test_report_generator as blocked


@pytest.fixture
def edge_case_data() -> dict:
    return {
        "edge_cases": [
            {
                "edge_case_id": "EDGE_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
                "edge_case_type": "ambiguous_timing",
                "edge_case_description": "Normal-mode timing is not fully defined.",
            },
            {
                "edge_case_id": "EDGE_REQ_I2C_003_001",
                "requirement_id": "REQ_I2C_003",
                "edge_case_type": "optional_behaviour",
                "edge_case_description": "Fast-mode support may be optional.",
            },
            {
                "edge_case_id": "EDGE_REQ_I2C_003_002",
                "requirement_id": "REQ_I2C_003",
                "edge_case_type": "conditional_support",
                "edge_case_description": "Fast-mode behaviour depends on implementation support.",
            },
            {
                "edge_case_id": "EDGE_MISSING_REQ_ID",
                "edge_case_type": "bad_data",
                "edge_case_description": "This edge case has no requirement ID.",
            },
        ]
    }


@pytest.fixture
def edge_case_file(tmp_path: Path, edge_case_data: dict) -> Path:
    file_path = tmp_path / "generated-edge-cases.json"
    file_path.write_text(
        json.dumps(edge_case_data, indent=2),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def blocked_vplan_data() -> dict:
    return {
        "feature_list": [
            {
                "test_id": "TEST_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
                "coverage": "covered",
                "test_description": "Verify normal-mode operation.",
                "test_constraints": "None specified",
            },
            {
                "test_id": "TEST_REQ_I2C_002_001",
                "requirement_id": "REQ_I2C_002",
                "coverage": "blocked",
                "test_description": "Verify SCL timing.",
                "test_constraints": "Timing is not specified.",
            },
            {
                "test_id": "TEST_REQ_I2C_003_001",
                "requirement_id": "REQ_I2C_003",
                "coverage": "partially_covered",
                "test_description": "Verify fast-mode support.",
                "test_constraints": "Fast-mode behaviour is implementation-dependent.",
            },
            {
                "test_id": "TEST_REQ_I2C_004_001",
                "requirement_id": "REQ_I2C_004",
                "coverage": "blocked",
                "test_description": "Verify interrupt pass/fail behaviour.",
                "test_constraints": "Requirement does not define observable pass/fail criteria.",
            },
        ]
    }


@pytest.fixture
def blocked_vplan_file(tmp_path: Path, blocked_vplan_data: dict) -> Path:
    file_path = tmp_path / "blocked-vplan.json"
    file_path.write_text(
        json.dumps(blocked_vplan_data, indent=2),
        encoding="utf-8",
    )
    return file_path


# ---------------------------------------------------------------------------
# load_json
# ---------------------------------------------------------------------------


def test_load_json_loads_valid_json(blocked_vplan_file):
    result = blocked.load_json(blocked_vplan_file)

    assert isinstance(result, dict)
    assert "feature_list" in result


def test_load_json_accepts_string_path(blocked_vplan_file):
    result = blocked.load_json(str(blocked_vplan_file))

    assert isinstance(result, dict)
    assert "feature_list" in result


def test_load_json_raises_for_missing_file(tmp_path):
    missing_file = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        blocked.load_json(missing_file)


def test_load_json_raises_for_malformed_json(malformed_json_file):
    with pytest.raises(json.JSONDecodeError):
        blocked.load_json(malformed_json_file)


# ---------------------------------------------------------------------------
# build_edge_case_lookup
# ---------------------------------------------------------------------------


def test_build_edge_case_lookup_groups_edge_cases_by_requirement_id(edge_case_data):
    result = blocked.build_edge_case_lookup(edge_case_data)

    assert set(result.keys()) == {
        "REQ_I2C_001",
        "REQ_I2C_003",
    }

    assert len(result["REQ_I2C_001"]) == 1
    assert len(result["REQ_I2C_003"]) == 2


def test_build_edge_case_lookup_skips_edge_cases_missing_requirement_id():
    edge_case_data = {
        "edge_cases": [
            {
                "edge_case_id": "EDGE_VALID",
                "requirement_id": "REQ_I2C_001",
            },
            {
                "edge_case_id": "EDGE_MISSING_REQUIREMENT",
            },
            {
                "edge_case_id": "EDGE_EMPTY_REQUIREMENT",
                "requirement_id": "",
            },
        ]
    }

    result = blocked.build_edge_case_lookup(edge_case_data)

    assert result == {
        "REQ_I2C_001": [
            {
                "edge_case_id": "EDGE_VALID",
                "requirement_id": "REQ_I2C_001",
            }
        ]
    }


def test_build_edge_case_lookup_returns_empty_dict_when_no_edge_cases_key():
    result = blocked.build_edge_case_lookup({})

    assert result == {}


def test_build_edge_case_lookup_returns_empty_dict_for_empty_edge_cases():
    result = blocked.build_edge_case_lookup({"edge_cases": []})

    assert result == {}


# ---------------------------------------------------------------------------
# infer_required_clarification
# ---------------------------------------------------------------------------


def test_infer_required_clarification_for_implementation_dependent_constraint():
    row = {"test_constraints": "This is implementation-dependent."}

    result = blocked.infer_required_clarification(row, [])

    assert (
        result == "Confirm implementation-specific configuration before verification."
    )


def test_infer_required_clarification_for_implementation_dependent_with_space():
    row = {"test_constraints": "This is implementation dependent."}

    result = blocked.infer_required_clarification(row, [])

    assert (
        result == "Confirm implementation-specific configuration before verification."
    )


def test_infer_required_clarification_for_missing_observable_criteria():
    row = {
        "test_constraints": "Requirement does not define observable pass/fail criteria."
    }

    result = blocked.infer_required_clarification(row, [])

    assert result == "Define observable pass/fail criteria for this requirement."


def test_infer_required_clarification_for_not_define_observable():
    row = {"test_constraints": "Does not define observable output."}

    result = blocked.infer_required_clarification(row, [])

    assert result == "Define observable pass/fail criteria for this requirement."


def test_infer_required_clarification_for_not_specified_constraint():
    row = {"test_constraints": "Timing is not specified."}

    result = blocked.infer_required_clarification(row, [])

    assert (
        result
        == "Provide the missing signal, timing, configuration, or behavioural detail."
    )


def test_infer_required_clarification_for_unspecified_constraint():
    row = {"test_constraints": "Reset behaviour is unspecified."}

    result = blocked.infer_required_clarification(row, [])

    assert (
        result
        == "Provide the missing signal, timing, configuration, or behavioural detail."
    )


def test_infer_required_clarification_for_related_edge_cases():
    row = {"test_constraints": "None specified"}

    related_edge_cases = [
        {
            "edge_case_id": "EDGE_REQ_I2C_001_001",
            "requirement_id": "REQ_I2C_001",
        }
    ]

    result = blocked.infer_required_clarification(row, related_edge_cases)

    assert (
        result
        == "Clarify the edge-case behaviour before treating this requirement as fully testable."
    )


def test_infer_required_clarification_default_message():
    row = {"test_constraints": "Review manually."}

    result = blocked.infer_required_clarification(row, [])

    assert (
        result
        == "Review requirement wording and provide enough detail for verification."
    )


def test_infer_required_clarification_handles_missing_constraints_key():
    row = {}

    result = blocked.infer_required_clarification(row, [])

    assert (
        result
        == "Review requirement wording and provide enough detail for verification."
    )


def test_infer_required_clarification_is_case_insensitive():
    row = {"test_constraints": "This is IMPLEMENTATION-DEPENDENT."}

    result = blocked.infer_required_clarification(row, [])

    assert (
        result == "Confirm implementation-specific configuration before verification."
    )


# ---------------------------------------------------------------------------
# export_blocked_test_report
# ---------------------------------------------------------------------------


def test_export_blocked_test_report_creates_report_file(
    blocked_vplan_file,
    edge_case_file,
):
    output_file = blocked.export_blocked_test_report(
        blocked_vplan_file,
        edge_case_file,
    )

    assert isinstance(output_file, Path)
    assert output_file.exists()
    assert output_file.name.startswith("blocked_test_report_")
    assert output_file.name.endswith(".json")

    output_file.unlink()


def test_export_blocked_test_report_writes_expected_metadata(
    blocked_vplan_file,
    edge_case_file,
):
    output_file = blocked.export_blocked_test_report(
        blocked_vplan_file,
        edge_case_file,
    )

    report = json.loads(output_file.read_text(encoding="utf-8"))

    assert report["metadata"]["vplan_file"] == str(blocked_vplan_file)
    assert report["metadata"]["edge_case_file"] == str(edge_case_file)
    assert report["metadata"]["number_of_blocked_tests"] == 2
    assert report["metadata"]["number_of_partially_covered_tests"] == 1
    assert "date_created" in report["metadata"]
    assert "time_created" in report["metadata"]

    output_file.unlink()


def test_export_blocked_test_report_separates_blocked_and_partially_covered_tests(
    blocked_vplan_file,
    edge_case_file,
):
    output_file = blocked.export_blocked_test_report(
        blocked_vplan_file,
        edge_case_file,
    )

    report = json.loads(output_file.read_text(encoding="utf-8"))

    blocked_tests = report["blocked_tests"]
    partially_covered_tests = report["partially_covered_tests"]

    assert len(blocked_tests) == 2
    assert len(partially_covered_tests) == 1

    assert [test["test_id"] for test in blocked_tests] == [
        "TEST_REQ_I2C_002_001",
        "TEST_REQ_I2C_004_001",
    ]

    assert partially_covered_tests[0]["test_id"] == "TEST_REQ_I2C_003_001"

    output_file.unlink()


def test_export_blocked_test_report_excludes_covered_tests(
    blocked_vplan_file,
    edge_case_file,
):
    output_file = blocked.export_blocked_test_report(
        blocked_vplan_file,
        edge_case_file,
    )

    report = json.loads(output_file.read_text(encoding="utf-8"))

    all_reported_test_ids = {
        test["test_id"]
        for test in report["blocked_tests"] + report["partially_covered_tests"]
    }

    assert "TEST_REQ_I2C_001_001" not in all_reported_test_ids

    output_file.unlink()


def test_export_blocked_test_report_includes_required_clarification(
    blocked_vplan_file,
    edge_case_file,
):
    output_file = blocked.export_blocked_test_report(
        blocked_vplan_file,
        edge_case_file,
    )

    report = json.loads(output_file.read_text(encoding="utf-8"))

    blocked_by_requirement_id = {
        test["requirement_id"]: test for test in report["blocked_tests"]
    }

    partially_covered_by_requirement_id = {
        test["requirement_id"]: test for test in report["partially_covered_tests"]
    }

    assert blocked_by_requirement_id["REQ_I2C_002"]["required_clarification"] == (
        "Provide the missing signal, timing, configuration, or behavioural detail."
    )

    assert blocked_by_requirement_id["REQ_I2C_004"]["required_clarification"] == (
        "Define observable pass/fail criteria for this requirement."
    )

    assert partially_covered_by_requirement_id["REQ_I2C_003"][
        "required_clarification"
    ] == ("Confirm implementation-specific configuration before verification.")

    output_file.unlink()


def test_export_blocked_test_report_includes_related_edge_cases(
    blocked_vplan_file,
    edge_case_file,
):
    output_file = blocked.export_blocked_test_report(
        blocked_vplan_file,
        edge_case_file,
    )

    report = json.loads(output_file.read_text(encoding="utf-8"))

    partially_covered_test = report["partially_covered_tests"][0]

    assert partially_covered_test["requirement_id"] == "REQ_I2C_003"
    assert partially_covered_test["related_edge_cases"] == [
        {
            "edge_case_id": "EDGE_REQ_I2C_003_001",
            "edge_case_type": "optional_behaviour",
            "edge_case_description": "Fast-mode support may be optional.",
        },
        {
            "edge_case_id": "EDGE_REQ_I2C_003_002",
            "edge_case_type": "conditional_support",
            "edge_case_description": "Fast-mode behaviour depends on implementation support.",
        },
    ]

    output_file.unlink()


def test_export_blocked_test_report_uses_empty_related_edge_cases_when_none_match(
    blocked_vplan_file,
    edge_case_file,
):
    output_file = blocked.export_blocked_test_report(
        blocked_vplan_file,
        edge_case_file,
    )

    report = json.loads(output_file.read_text(encoding="utf-8"))

    blocked_by_requirement_id = {
        test["requirement_id"]: test for test in report["blocked_tests"]
    }

    assert blocked_by_requirement_id["REQ_I2C_002"]["related_edge_cases"] == []
    assert blocked_by_requirement_id["REQ_I2C_004"]["related_edge_cases"] == []

    output_file.unlink()


def test_export_blocked_test_report_handles_no_blocked_or_partial_tests(
    tmp_path,
    edge_case_file,
):
    vplan_data = {
        "feature_list": [
            {
                "test_id": "TEST_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
                "coverage": "covered",
                "test_description": "Covered test.",
                "test_constraints": "None specified",
            }
        ]
    }

    vplan_file = tmp_path / "covered-only-vplan.json"
    vplan_file.write_text(json.dumps(vplan_data, indent=2), encoding="utf-8")

    output_file = blocked.export_blocked_test_report(vplan_file, edge_case_file)

    report = json.loads(output_file.read_text(encoding="utf-8"))

    assert report["metadata"]["number_of_blocked_tests"] == 0
    assert report["metadata"]["number_of_partially_covered_tests"] == 0
    assert report["blocked_tests"] == []
    assert report["partially_covered_tests"] == []

    output_file.unlink()


def test_export_blocked_test_report_handles_missing_feature_list(
    tmp_path,
    edge_case_file,
):
    vplan_file = tmp_path / "missing-feature-list.json"
    vplan_file.write_text(
        json.dumps({"metadata": {"name": "No rows"}}), encoding="utf-8"
    )

    output_file = blocked.export_blocked_test_report(vplan_file, edge_case_file)

    report = json.loads(output_file.read_text(encoding="utf-8"))

    assert report["metadata"]["number_of_blocked_tests"] == 0
    assert report["metadata"]["number_of_partially_covered_tests"] == 0
    assert report["blocked_tests"] == []
    assert report["partially_covered_tests"] == []

    output_file.unlink()


def test_export_blocked_test_report_handles_missing_edge_cases_key(
    tmp_path,
    blocked_vplan_file,
):
    edge_case_file = tmp_path / "missing-edge-cases.json"
    edge_case_file.write_text(
        json.dumps({"metadata": {"name": "No edge cases"}}), encoding="utf-8"
    )

    output_file = blocked.export_blocked_test_report(blocked_vplan_file, edge_case_file)

    report = json.loads(output_file.read_text(encoding="utf-8"))

    for record in report["blocked_tests"] + report["partially_covered_tests"]:
        assert record["related_edge_cases"] == []

    output_file.unlink()


def test_export_blocked_test_report_accepts_string_paths(
    blocked_vplan_file,
    edge_case_file,
):
    output_file = blocked.export_blocked_test_report(
        str(blocked_vplan_file),
        str(edge_case_file),
    )

    assert output_file.exists()

    output_file.unlink()


def test_export_blocked_test_report_raises_for_missing_vplan_file(
    tmp_path,
    edge_case_file,
):
    missing_vplan_file = tmp_path / "missing-vplan.json"

    with pytest.raises(FileNotFoundError):
        blocked.export_blocked_test_report(missing_vplan_file, edge_case_file)


def test_export_blocked_test_report_raises_for_missing_edge_case_file(
    blocked_vplan_file,
    tmp_path,
):
    missing_edge_case_file = tmp_path / "missing-edge-cases.json"

    with pytest.raises(FileNotFoundError):
        blocked.export_blocked_test_report(blocked_vplan_file, missing_edge_case_file)


def test_export_blocked_test_report_raises_for_malformed_vplan_json(
    malformed_json_file,
    edge_case_file,
):
    with pytest.raises(json.JSONDecodeError):
        blocked.export_blocked_test_report(malformed_json_file, edge_case_file)


def test_export_blocked_test_report_raises_for_malformed_edge_case_json(
    blocked_vplan_file,
    malformed_json_file,
):
    with pytest.raises(json.JSONDecodeError):
        blocked.export_blocked_test_report(blocked_vplan_file, malformed_json_file)
