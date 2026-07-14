from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from Backend.coverage import granularity_adequacy as metric

from types import SimpleNamespace


class FakeCallbackContext:
    def __init__(self):
        self.callback = SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            total_cost=0.001,
        )

    def __enter__(self):
        return self.callback

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_granularity_assessment_validation():
    assessment = metric.GranularityAssessment(
        requirement_id="REQ_1",
        suitable_detail=True,
        granularity_label="suitable_detail",
        reason="Specific test.",
        linked_tests=["T1"],
    )
    assert assessment.suitable_detail is True

    with pytest.raises(ValidationError):
        metric.GranularityAssessment(
            requirement_id="REQ_1",
            suitable_detail=True,
            granularity_label="invalid",
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
    assert metric.get_test_id({}, 0) == "VPLAN_ITEM_001"


def test_group_vplan_items_ignores_items_without_requirement_id():
    result = metric.group_vplan_items_by_requirement_id(
        [{"requirement_id": "REQ_1"}, {"id": "REQ_2"}, {"test_id": "T3"}]
    )
    assert set(result) == {"REQ_1", "REQ_2"}


def test_build_requirement_payload_simplifies_tests():
    payload = metric.build_requirement_payload(
        {"id": "REQ_1", "text": "Text", "source_section": "A1"},
        [{"test_id": "T1", "test_description": "Verify", "extra": "ignored"}],
    )

    assert payload["requirement"]["id"] == "REQ_1"
    assert payload["linked_vplan_items"][0]["test_id"] == "T1"
    assert "extra" not in payload["linked_vplan_items"][0]


def test_assess_requirement_without_id_does_not_call_agent(monkeypatch):
    def fail_if_agent_requested():
        raise AssertionError(
            "Agent should not be created for a requirement without an ID."
        )

    monkeypatch.setattr(
        metric,
        "get_agent",
        fail_if_agent_requested,
    )

    result = metric.assess_requirement_granularity(
        {},
        [{"test_id": "T1"}],
    )

    assert result.requirement_id == "UNKNOWN_REQUIREMENT_ID"
    assert result.suitable_detail is False
    assert result.granularity_label == "unclear"
    assert result.linked_tests == []


def test_assess_unmapped_requirement_does_not_call_agent(monkeypatch):
    def fail_if_agent_requested():
        raise AssertionError("Agent should not be created for an unmapped requirement.")

    monkeypatch.setattr(
        metric,
        "get_agent",
        fail_if_agent_requested,
    )

    result = metric.assess_requirement_granularity(
        {
            "id": "REQ_1",
            "text": "Requirement",
        },
        [],
    )

    assert result.requirement_id == "REQ_1"
    assert result.suitable_detail is False
    assert result.granularity_label == "not_mapped"
    assert result.linked_tests == []


def test_calculate_granularity_adequacy_without_running_agent(monkeypatch):
    def fake_assess(requirement, linked_vplan_items):
        if linked_vplan_items:
            return metric.GranularityAssessment(
                requirement_id=requirement["id"],
                suitable_detail=True,
                granularity_label="suitable_detail",
                reason="Specific enough.",
                linked_tests=[linked_vplan_items[0]["test_id"]],
            )
        return metric.GranularityAssessment(
            requirement_id=requirement["id"],
            suitable_detail=False,
            granularity_label="not_mapped",
            reason="No test.",
            linked_tests=[],
        )

    monkeypatch.setattr(metric, "assess_requirement_granularity", fake_assess)
    monkeypatch.setattr(metric, "get_openai_callback", FakeCallbackContext)
    monkeypatch.setattr(
        metric,
        "normalise_usage",
        lambda **kwargs: {"total_tokens": kwargs["total_tokens"]},
    )

    result = metric.calculate_granularity_adequacy(
        [
            {"id": "REQ_1", "text": "Mapped", "source_section": "A1"},
            {"id": "REQ_2", "text": "Unmapped", "source_section": "A1"},
        ],
        [{"test_id": "T1", "requirement_id": "REQ_1"}],
    )

    assert result["mapped_requirements"] == 1
    assert result["requirements_covered_at_suitable_detail"] == 1
    assert result["requirements_not_mapped"] == 1
    assert result["granularity_adequacy"] == 100.0
    assert result["usage"] == {"total_tokens": 15}
    assert result["assessments"][0]["requirement_text"] == "Mapped"


def test_run_granularity_adequacy_rejects_non_object_spec(tmp_path, write_json):
    spec = write_json(tmp_path / "spec.json", [])
    vplan = write_json(tmp_path / "vplan.json", {"feature_list": []})

    with pytest.raises(ValueError, match="JSON object"):
        metric.run_granularity_adequacy(spec, vplan)


def test_print_summary(capsys):
    metric.print_granularity_adequacy_summary(
        {
            "total_requirements": 1,
            "mapped_requirements": 1,
            "requirements_covered_at_suitable_detail": 1,
            "requirements_not_mapped": 0,
            "granularity_adequacy": 100.0,
            "label_counts": {"suitable_detail": 1},
            "assessments": [],
        }
    )
    assert "Granularity Adequacy" in capsys.readouterr().out
