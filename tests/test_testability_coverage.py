import pytest
from pydantic import ValidationError

from Backend.coverage import testability_coverage as metric


def test_testability_assessment_validation():
    assessment = metric.TestabilityAssessment(
        requirement_id="REQ_1",
        testability_label="fully_testable",
        is_testable=True,
        reason="Clear expected result.",
        linked_tests=["T1"],
    )
    assert assessment.is_testable is True

    with pytest.raises(ValidationError):
        metric.TestabilityAssessment(
            requirement_id="REQ_1",
            testability_label="invalid",
            is_testable=False,
            reason="Bad label.",
        )


def test_extractors_and_ids():
    assert metric.extract_spec_requirements({"requirements": []}) == []
    with pytest.raises(ValueError):
        metric.extract_spec_requirements({"requirements": {}})

    row = {"test_id": "T1"}
    assert metric.extract_vplan_items([row]) == [row]
    assert metric.extract_vplan_items({"feature_list": [row]}) == [row]
    assert metric.get_requirement_id({"id": 3}) == "3"
    assert metric.get_test_id({}, 1) == "VPLAN_ITEM_002"


def test_group_vplan_items_by_requirement_id():
    grouped = metric.group_vplan_items_by_requirement_id(
        [{"requirement_id": "REQ_1"}, {"id": "REQ_2"}, {"test_id": "T3"}]
    )
    assert set(grouped) == {"REQ_1", "REQ_2"}


def test_build_requirement_payload():
    payload = metric.build_requirement_payload(
        {"id": "REQ_1", "text": "Text"},
        [{"test_id": "T1", "expected_results": ["Pass"], "extra": "ignored"}],
    )

    assert payload["requirement"]["id"] == "REQ_1"
    assert payload["linked_vplan_items"][0]["expected_results"] == ["Pass"]
    assert "extra" not in payload["linked_vplan_items"][0]


def test_assess_without_id_does_not_call_agent(monkeypatch):
    monkeypatch.setattr(
        metric.agent,
        "invoke",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("agent ran")),
    )

    result = metric.assess_requirement_testability({}, [{"test_id": "T1"}])

    assert result.requirement_id == "UNKNOWN_REQUIREMENT_ID"
    assert result.testability_label == "unclear"


def test_assess_unmapped_does_not_call_agent(monkeypatch):
    monkeypatch.setattr(
        metric.agent,
        "invoke",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("agent ran")),
    )

    result = metric.assess_requirement_testability(
        {"id": "REQ_1", "text": "Requirement"}, []
    )

    assert result.testability_label == "not_mapped"
    assert result.is_testable is False


def test_calculate_testability_coverage_without_running_agent(monkeypatch):
    def fake_assess(requirement, linked_vplan_items):
        if not linked_vplan_items:
            return metric.TestabilityAssessment(
                requirement_id=requirement["id"],
                testability_label="not_mapped",
                is_testable=False,
                reason="No mapping.",
                linked_tests=[],
            )
        is_testable = requirement["id"] == "REQ_1"
        return metric.TestabilityAssessment(
            requirement_id=requirement["id"],
            testability_label=(
                "fully_testable" if is_testable else "partially_testable"
            ),
            is_testable=is_testable,
            reason="Assessment.",
            linked_tests=[linked_vplan_items[0]["test_id"]],
        )

    monkeypatch.setattr(metric, "assess_requirement_testability", fake_assess)

    result = metric.calculate_testability_coverage(
        [
            {"id": "REQ_1"},
            {"id": "REQ_2"},
            {"id": "REQ_3"},
        ],
        [
            {"test_id": "T1", "requirement_id": "REQ_1"},
            {"test_id": "T2", "requirement_id": "REQ_2"},
        ],
    )

    assert result["mapped_spec_items"] == 2
    assert result["mapped_items_with_testable_vplan_entry"] == 1
    assert result["mapped_items_without_testable_vplan_entry"] == 1
    assert result["requirements_not_mapped"] == 1
    assert result["testability_coverage"] == 50.0


def test_run_testability_coverage_rejects_non_object_spec(tmp_path, write_json):
    spec = write_json(tmp_path / "spec.json", [])
    vplan = write_json(tmp_path / "vplan.json", {"feature_list": []})

    with pytest.raises(ValueError, match="JSON object"):
        metric.run_testability_coverage(spec, vplan)


def test_print_summary(capsys):
    metric.print_testability_coverage_summary(
        {
            "total_requirements": 1,
            "mapped_spec_items": 1,
            "mapped_items_with_testable_vplan_entry": 1,
            "mapped_items_without_testable_vplan_entry": 0,
            "requirements_not_mapped": 0,
            "testability_coverage": 100.0,
            "label_counts": {"fully_testable": 1},
            "assessments": [],
        }
    )
    assert "Testability Coverage" in capsys.readouterr().out
