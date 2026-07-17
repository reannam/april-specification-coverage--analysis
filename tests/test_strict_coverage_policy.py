import pytest
from pydantic import ValidationError

from Backend.Coverage.coverage_status_verifier import (
    classify_requirement_status,
    verify_requirement_coverage,
)
from Backend.vPlan.pre_processing.data_class import VPlanColumns


def make_row(**overrides):
    row = {
        "test_id": "TEST_001",
        "requirement_id": "REQ_001",
        "scenario_type": "nominal",
        "category": "Register Access",
        "priority": 3,
        "test_name": "Verify Register Read",
        "test_description": "Read the status register.",
        "test_constraints": "Use the address stated by the requirement.",
        "test_steps": ["Read the status register at the stated address."],
        "expected_results": ["The stated status value is returned."],
        "coverage": "covered",
    }
    row.update(overrides)
    return row


def test_uncovered_row_is_forcibly_cleared():
    row = VPlanColumns.model_validate(
        make_row(
            coverage="uncovered",
            test_name="Suggested Test",
            test_description="A speculative test.",
            test_steps=["Guess a value."],
            expected_results=["Assume success."],
        )
    )

    assert row.test_name == ""
    assert row.test_description == ""
    assert row.test_steps == []
    assert row.expected_results == []


@pytest.mark.parametrize("coverage", ["covered", "partially_covered"])
def test_non_uncovered_rows_require_real_test_content(coverage):
    with pytest.raises(ValidationError):
        VPlanColumns.model_validate(
            make_row(
                coverage=coverage,
                test_description="",
                test_steps=[],
                expected_results=[],
            )
        )


def test_complete_covered_row_without_ambiguity_is_covered():
    status, _ = classify_requirement_status(
        requirement_id="REQ_001",
        linked_tests=[make_row()],
        linked_edge_cases=[],
        linked_weak_word_flags=[],
    )

    assert status == "Covered"


def test_covered_label_with_incomplete_content_is_uncovered():
    status, _ = classify_requirement_status(
        requirement_id="REQ_001",
        linked_tests=[make_row(test_steps=[], expected_results=[])],
        linked_edge_cases=[],
        linked_weak_word_flags=[],
    )

    assert status == "Uncovered"


def test_uncovered_label_never_counts_as_executable_evidence():
    status, _ = classify_requirement_status(
        requirement_id="REQ_001",
        linked_tests=[make_row(coverage="uncovered")],
        linked_edge_cases=[],
        linked_weak_word_flags=[],
    )

    assert status == "Uncovered"


def test_complete_test_with_ambiguity_is_only_partially_covered():
    status, _ = classify_requirement_status(
        requirement_id="REQ_001",
        linked_tests=[make_row()],
        linked_edge_cases=[{"requirement_id": "REQ_001"}],
        linked_weak_word_flags=[],
    )

    assert status == "Partially covered"


def test_mixed_complete_and_uncovered_rows_are_partially_covered():
    status, _ = classify_requirement_status(
        requirement_id="REQ_001",
        linked_tests=[
            make_row(),
            make_row(
                test_id="TEST_002",
                coverage="uncovered",
                test_name="",
                test_description="",
                test_steps=[],
                expected_results=[],
            ),
        ],
        linked_edge_cases=[],
        linked_weak_word_flags=[],
    )

    assert status == "Partially covered"


def test_weak_language_issues_are_used_by_final_verifier():
    result = verify_requirement_coverage(
        spec_json={"requirements": [{"id": "REQ_001", "text": "A feature may exist."}]},
        vplan_json={"feature_list": [make_row()]},
        edge_cases_json={"edge_cases": []},
        weak_words_json={
            "issues": [
                {
                    "requirement_id": "REQ_001",
                    "issue_type": "weak_or_optional_language",
                }
            ]
        },
    )

    assert result["labelled_requirements"][0]["verified_coverage_status"] == (
        "Partially covered"
    )
