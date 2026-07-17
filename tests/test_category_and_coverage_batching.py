import pytest

from Backend.Coverage import granularity_adequacy, testability_coverage
from Backend.config import REQUIREMENT_CATEGORY_MODEL
from Backend.vPlan.agents import requirement_category_agent
from Backend.vPlan.agents.requirement_category_agent import (
    _validated_assignments,
    create_category_model,
)
from Backend.vPlan.agents.vplan_generator_utils import build_category_batches
from Backend.vPlan.agents.vplan_category_agent import (
    deterministic_test_name,
    has_usable_test_name,
)
from Backend.vPlan.pre_processing.data_class import (
    RequirementCategoryAssignment,
    RequirementCategoryAssignments,
    RequirementCategoryDefinition,
    RequirementTaxonomy,
)


def test_requirement_taxonomy_cannot_expand_beyond_twelve_parents():
    with pytest.raises(ValueError):
        RequirementTaxonomy(
            categories=[
                RequirementCategoryDefinition(
                    category=f"Category {index}",
                    description="Engineering concern",
                    subcategories=["Behaviour"],
                )
                for index in range(13)
            ]
        )


def test_requirement_category_model_disables_reasoning_for_schema_tools(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        requirement_category_agent,
        "ChatOpenAI",
        FakeChatOpenAI,
    )

    create_category_model()

    assert captured == {
        "model": REQUIREMENT_CATEGORY_MODEL.removeprefix("openai:"),
        "reasoning_effort": "none",
    }


def test_identifier_shaped_test_name_is_rejected_and_has_description_fallback():
    test = {
        "test_id": "TC_REQ_A2_001",
        "requirement_id": "REQ_A2_001",
        "test_name": "TC_REQ_A2_001",
        "test_description": "Verify the write response completion signal",
        "scenario_type": "nominal",
    }

    assert has_usable_test_name(test) is False
    assert deterministic_test_name(test) == "The Write Response Completion Signal"


def test_assignment_must_use_the_fixed_parent_and_subcategory():
    response = RequirementCategoryAssignments(
        assignments=[
            RequirementCategoryAssignment(
                requirement_id="REQ_1",
                category="Protocol",
                subcategory="Transfers",
            )
        ]
    )

    assert _validated_assignments(
        response,
        [{"id": "REQ_1"}],
        {"Protocol": {"Transfers", "Timing"}},
    ) == {"REQ_1": ("Protocol", "Transfers")}


def test_category_batches_join_related_requirements_across_chapters():
    requirements = [
        {
            "id": "REQ_A2",
            "requirement_category": "Protocol",
            "requirement_subcategory": "Transfers",
            "source_section": "A2",
        },
        {
            "id": "REQ_SEC",
            "requirement_category": "Security",
            "requirement_subcategory": "Access",
            "source_section": "A3",
        },
        {
            "id": "REQ_A5",
            "requirement_category": "Protocol",
            "requirement_subcategory": "Transfers",
            "source_section": "A5",
        },
    ]

    batches = build_category_batches(requirements, max_batch_size=10)

    assert [batch["category"] for batch in batches] == ["Protocol", "Security"]
    assert [item["id"] for item in batches[0]["requirements"]] == [
        "REQ_A2",
        "REQ_A5",
    ]
    assert all(
        item["planning_category"] == "Protocol" for item in batches[0]["requirements"]
    )
    assert all(
        item["planning_subcategory"] == "Transfers"
        for item in batches[0]["requirements"]
    )


def test_oversized_category_is_still_bounded():
    requirements = [
        {"id": f"REQ_{index}", "category": "Protocol"} for index in range(5)
    ]

    batches = build_category_batches(requirements, max_batch_size=2)

    assert [len(batch["requirements"]) for batch in batches] == [2, 2, 1]
    assert [batch["category_part"] for batch in batches] == [1, 2, 3]


def test_granularity_uses_batched_results_and_marks_missing_output_unclear(
    monkeypatch,
):
    requirements = [
        {"id": "REQ_1", "text": "First"},
        {"id": "REQ_2", "text": "Second"},
        {"id": "REQ_3", "text": "Unmapped"},
    ]
    vplan = [
        {"test_id": "TEST_1", "requirement_id": "REQ_1"},
        {"test_id": "TEST_2", "requirement_id": "REQ_2"},
    ]

    def fake_batches(**kwargs):
        assert len(kwargs["payloads"]) == 2
        return (
            [
                granularity_adequacy.GranularityAssessment(
                    requirement_id="REQ_1",
                    suitable_detail=True,
                    granularity_label="suitable_detail",
                    reason="Specific test.",
                    linked_tests=["TEST_1"],
                )
            ],
            {"number_of_batches": 1, "failed_batches": []},
        )

    monkeypatch.setattr(granularity_adequacy, "run_review_batches", fake_batches)
    result = granularity_adequacy.calculate_granularity_adequacy(requirements, vplan)

    labels = {
        item["requirement_id"]: item["granularity_label"]
        for item in result["assessments"]
    }
    assert labels == {
        "REQ_1": "suitable_detail",
        "REQ_2": "unclear",
        "REQ_3": "not_mapped",
    }
    assert result["usage"]["number_of_batches"] == 1


def test_granularity_cannot_call_a_linked_requirement_not_mapped(monkeypatch):
    requirements = [{"id": "REQ_1", "text": "First"}]
    vplan = [{"test_id": "TEST_1", "requirement_id": "REQ_1"}]

    def fake_batches(**kwargs):
        return (
            [
                granularity_adequacy.GranularityAssessment(
                    requirement_id="REQ_1",
                    suitable_detail=False,
                    granularity_label="not_mapped",
                    reason="Incorrect model result.",
                    linked_tests=["TEST_1"],
                )
            ],
            {
                "number_of_batches": 1,
                "failed_batches": [],
                "vplan_items_submitted": 1,
                "test_ids_submitted": ["TEST_1"],
            },
        )

    monkeypatch.setattr(granularity_adequacy, "run_review_batches", fake_batches)
    result = granularity_adequacy.calculate_granularity_adequacy(requirements, vplan)

    assert result["mapped_requirements"] == 1
    assert result["requirements_not_mapped"] == 0
    assert result["assessments"][0]["granularity_label"] == "unclear"
    assert result["vplan_item_audit"]["test_ids_submitted_to_model"] == [
        "TEST_1"
    ]


def test_testability_returns_batch_usage(monkeypatch):
    requirements = [{"id": "REQ_1", "text": "First"}]
    vplan = [{"test_id": "TEST_1", "requirement_id": "REQ_1"}]

    def fake_batches(**kwargs):
        return (
            [
                testability_coverage.TestabilityAssessment(
                    requirement_id="REQ_1",
                    testability_label="fully_testable",
                    is_testable=True,
                    reason="Complete test.",
                    linked_tests=["TEST_1"],
                )
            ],
            {"number_of_batches": 1, "failed_batches": []},
        )

    monkeypatch.setattr(testability_coverage, "run_review_batches", fake_batches)
    result = testability_coverage.calculate_testability_coverage(requirements, vplan)

    assert result["testability_coverage"] == 100.0
    assert result["usage"]["failed_batches"] == []


@pytest.mark.parametrize(
    "module",
    [granularity_adequacy, testability_coverage],
)
def test_coverage_payload_uses_only_explicitly_cited_related_requirements(module):
    primary = {"id": "REQ_A2", "text": "Transfer shall use the configured width."}
    requirements_by_id = {
        "REQ_A2": primary,
        "REQ_A5": {"id": "REQ_A5", "text": "The configured width shall be 32 bits."},
        "REQ_SIMILAR": {
            "id": "REQ_SIMILAR",
            "text": "A different transfer also uses a width.",
        },
    }
    linked_tests = [
        {
            "test_id": "TEST_A2",
            "requirement_id": "REQ_A2",
            "supporting_requirement_ids": ["REQ_A5", "REQ_MISSING"],
        }
    ]

    payload = module.build_requirement_payload(
        primary,
        linked_tests,
        requirements_by_id,
    )

    assert payload["supporting_requirements"] == [
        {
            "id": "REQ_A5",
            "text": "The configured width shall be 32 bits.",
            "source_section": None,
            "requirement_category": None,
            "requirement_subcategory": None,
        }
    ]
