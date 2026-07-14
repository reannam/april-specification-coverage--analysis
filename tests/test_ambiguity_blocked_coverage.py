import json
from pathlib import Path

import pytest

from Backend.coverage import ambiguity_blocked_coverage as metric


def test_load_json_round_trip(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"value": 3}', encoding="utf-8")

    assert metric.load_json(path) == {"value": 3}


def test_load_json_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        metric.load_json(tmp_path / "missing.json")


def test_extractors_validate_top_level_lists():
    assert metric.extract_spec_requirements({"requirements": []}) == []
    assert metric.extract_labelled_requirements({"labelled_requirements": []}) == []

    with pytest.raises(ValueError):
        metric.extract_spec_requirements({"requirements": {}})

    with pytest.raises(ValueError):
        metric.extract_labelled_requirements({"labelled_requirements": {}})


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ({"id": "REQ_1"}, "REQ_1"),
        ({"requirement_id": 2}, "2"),
        ({}, None),
    ],
)
def test_get_requirement_key(requirement, expected):
    assert metric.get_requirement_key(requirement) == expected


def test_ambiguity_helpers():
    assert metric.has_ambiguity_signal({"linked_edge_cases": [{}]}) is True
    assert metric.has_ambiguity_signal({"linked_weak_word_flags": [{}]}) is True
    assert metric.has_ambiguity_signal({}) is False

    assert (
        metric.has_blocked_test(
            {"original_vplan_coverage_values": ["covered", "blocked"]}
        )
        is True
    )
    assert (
        metric.has_blocked_test({"original_vplan_coverage_values": ["covered"]})
        is False
    )


def test_is_ambiguity_blocked_from_status_or_combined_evidence():
    assert (
        metric.is_ambiguity_blocked(
            {"verified_coverage_status": "Ambiguous / not yet plannable"}
        )
        is True
    )

    assert (
        metric.is_ambiguity_blocked(
            {
                "verified_coverage_status": "Partially covered",
                "original_vplan_coverage_values": ["blocked"],
                "linked_edge_cases": [{"edge_case_id": "EDGE_1"}],
            }
        )
        is True
    )

    assert (
        metric.is_ambiguity_blocked(
            {
                "verified_coverage_status": "Partially covered",
                "original_vplan_coverage_values": ["blocked"],
            }
        )
        is False
    )


def test_calculate_ambiguity_blocked_coverage(
    sample_spec, sample_labelled_requirements
):
    result = metric.calculate_ambiguity_blocked_coverage(
        sample_spec["requirements"], sample_labelled_requirements
    )

    assert result["total_spec_items"] == 3
    assert result["spec_items_blocked_by_ambiguity"] == 1
    assert result["spec_items_not_blocked_by_ambiguity"] == 2
    assert result["ambiguity_blocked_coverage"] == 33.33
    assert (
        result["ambiguity_blocked_requirements"][0]["requirement_id"] == "REQ_A2_1_003"
    )
    assert result["ambiguity_blocked_requirements"][0]["linked_tests"] == ["TEST_003"]


def test_calculate_empty_input_returns_zero():
    result = metric.calculate_ambiguity_blocked_coverage([], [])

    assert result["ambiguity_blocked_coverage"] == 0.0
    assert result["spec_items_blocked_by_ambiguity"] == 0


def test_run_ambiguity_blocked_coverage_reads_files(
    tmp_path, write_json, sample_spec, sample_labelled_requirements
):
    spec_file = write_json(tmp_path / "spec.json", sample_spec)
    coverage_file = write_json(
        tmp_path / "coverage.json",
        {"labelled_requirements": sample_labelled_requirements},
    )

    result = metric.run_ambiguity_blocked_coverage(spec_file, coverage_file)

    assert result["spec_items_blocked_by_ambiguity"] == 1


def test_print_summary(capsys):
    metric.print_ambiguity_blocked_summary(
        {
            "total_spec_items": 2,
            "spec_items_blocked_by_ambiguity": 1,
            "spec_items_not_blocked_by_ambiguity": 1,
            "ambiguity_blocked_coverage": 50.0,
            "ambiguity_blocked_requirements": [{"requirement_id": "REQ_2"}],
        }
    )

    output = capsys.readouterr().out
    assert "Ambiguity-Blocked Coverage" in output
    assert "REQ_2" in output
