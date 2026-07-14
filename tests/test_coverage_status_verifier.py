import json

import pytest

from Backend.coverage import coverage_status_verifier as verifier


def test_duplicate_requirement_warning_contains_details():
    requirements = [
        {"id": "REQ_1", "text": "First", "source_section": "A1"},
        {"id": "REQ_1", "text": "Second", "source_section": "A2"},
        {"id": "REQ_2", "text": "Unique"},
    ]

    warnings = verifier.build_duplicate_requirement_id_warning(requirements)

    assert len(warnings) == 1
    assert warnings[0]["affected_requirement_ids"] == ["REQ_1"]
    assert len(warnings[0]["duplicate_details"]["REQ_1"]) == 2


def test_duplicate_requirement_warning_empty_when_unique():
    assert verifier.build_duplicate_requirement_id_warning([{"id": "REQ_1"}]) == []


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ([{"id": "REQ_1"}], [{"id": "REQ_1"}]),
        ({"requirements": [{"id": "REQ_1"}]}, [{"id": "REQ_1"}]),
        ({"feature_list": [{"id": "REQ_1"}]}, [{"id": "REQ_1"}]),
    ],
)
def test_extract_requirements(payload, expected):
    assert verifier.extract_requirements(payload) == expected


def test_extract_requirements_rejects_unknown_shape():
    with pytest.raises(ValueError):
        verifier.extract_requirements({})


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ([{"test_id": "T1"}], [{"test_id": "T1"}]),
        ({"feature_list": [{"test_id": "T1"}]}, [{"test_id": "T1"}]),
        ({"tests": [{"test_id": "T1"}]}, [{"test_id": "T1"}]),
    ],
)
def test_extract_vplan_tests(payload, expected):
    assert verifier.extract_vplan_tests(payload) == expected


def test_extract_items_supports_common_wrappers_and_filters_non_dicts():
    assert verifier.extract_items(None) == []
    assert verifier.extract_items([{"id": "A"}, "bad"]) == [{"id": "A"}]
    assert verifier.extract_items({"edge_cases": [{"id": "A"}]}) == [{"id": "A"}]
    assert verifier.extract_items({"weak_requirements": [{"id": "A"}]}) == [{"id": "A"}]


@pytest.mark.parametrize(
    ("test", "expected"),
    [
        ({"coverage": " covered "}, "covered"),
        ({"test_coverage": "PARTIALLY_COVERED"}, "partially_covered"),
        ({"status": "blocked"}, "blocked"),
        ({"coverage": "unknown"}, None),
    ],
)
def test_get_test_coverage(test, expected):
    assert verifier.get_test_coverage(test) == expected


@pytest.mark.parametrize(
    ("tests", "edges", "weak", "expected_status"),
    [
        ([], [], [], "Uncovered"),
        ([], [{}], [], "Ambiguous / not yet plannable"),
        ([{"coverage": "blocked"}], [{}], [], "Ambiguous / not yet plannable"),
        ([{"coverage": "blocked"}], [], [], "Partially covered"),
        ([{"coverage": "covered"}], [], [], "Covered"),
        ([{"coverage": "covered"}], [], [{}], "Partially covered"),
        ([{"coverage": "partially_covered"}], [], [], "Partially covered"),
        ([{"coverage": "unknown"}], [], [], "Partially covered"),
    ],
)
def test_classify_requirement_status(tests, edges, weak, expected_status):
    status, reason = verifier.classify_requirement_status("REQ_1", tests, edges, weak)

    assert status == expected_status
    assert reason


def test_verify_requirement_coverage_integrates_inputs():
    result = verifier.verify_requirement_coverage(
        spec_json={
            "requirements": [
                {"id": "REQ_1", "text": "Covered"},
                {"id": "REQ_2", "text": "Blocked"},
                {"text": "Missing ID"},
            ]
        },
        vplan_json={
            "feature_list": [
                {"test_id": "T1", "requirement_id": "REQ_1", "coverage": "covered"},
                {"test_id": "T2", "requirement_id": "REQ_2", "coverage": "blocked"},
            ]
        },
        edge_cases_json={"edge_cases": [{"requirement_id": "REQ_2"}]},
        weak_words_json={"weak_requirements": []},
    )

    statuses = [
        item["verified_coverage_status"] for item in result["labelled_requirements"]
    ]
    assert statuses == [
        "Covered",
        "Ambiguous / not yet plannable",
        "Ambiguous / not yet plannable",
    ]
    assert result["traceability"][0]["linked_test_ids"] == ["T1"]
    assert result["blocked_test_report"][0]["requirement_id"] == "REQ_2"
    assert result["metadata"]["number_of_requirements"] == 3


def test_run_coverage_status_verifier_writes_output(tmp_path, write_json):
    spec = write_json(tmp_path / "spec.json", {"requirements": [{"id": "REQ_1"}]})
    vplan = write_json(tmp_path / "vplan.json", {"feature_list": []})
    edges = write_json(tmp_path / "edges.json", {"edge_cases": []})
    weak = write_json(tmp_path / "weak.json", {"weak_requirements": []})
    output = tmp_path / "nested" / "coverage.json"

    result = verifier.run_coverage_status_verifier(spec, vplan, edges, weak, output)

    assert result["coverage_status_file"] == str(output)
    assert result["usage"] == {}
    assert (
        json.loads(output.read_text(encoding="utf-8"))["metadata"][
            "number_of_requirements"
        ]
        == 1
    )
