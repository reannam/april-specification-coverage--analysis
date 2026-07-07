import pytest
from pydantic import ValidationError

from Backend.pre_processing.data_class import (
    CoverageFinding,
    CoverageGraphState,
    CoverageReport,
    CoverageSummary,
    EdgeCaseCandidate,
    EdgeCaseCandidateList,
    GraphState,
    Table,
    VPlanColumns,
)

# ---------------------------------------------------------------------------
# VPlanColumns
# ---------------------------------------------------------------------------


def test_vplan_columns_accepts_valid_data():
    row = VPlanColumns(
        test_id="TEST_REQ_I2C_001_001",
        requirement_id="REQ_I2C_001",
        test_type="positive",
        test_description="Verify normal-mode operation.",
        test_constraints="None specified",
        test_steps=["Configure the controller.", "Observe the bus speed."],
        expected_results=["The controller operates at 100 Kbps."],
        coverage="covered",
    )

    assert row.test_id == "TEST_REQ_I2C_001_001"
    assert row.requirement_id == "REQ_I2C_001"
    assert row.test_type == "positive"
    assert row.coverage == "covered"


@pytest.mark.parametrize("test_type", ["positive", "negative"])
def test_vplan_columns_accepts_valid_test_types(test_type):
    row = VPlanColumns(
        test_id="TEST_REQ_I2C_001_001",
        requirement_id="REQ_I2C_001",
        test_type=test_type,
        test_description="Verify behaviour.",
        test_constraints="None specified",
        test_steps=["Step 1"],
        expected_results=["Expected result 1"],
        coverage="covered",
    )

    assert row.test_type == test_type


def test_vplan_columns_rejects_invalid_test_type():
    with pytest.raises(ValidationError):
        VPlanColumns(
            test_id="TEST_REQ_I2C_001_001",
            requirement_id="REQ_I2C_001",
            test_type="edge",
            test_description="Verify behaviour.",
            test_constraints="None specified",
            test_steps=["Step 1"],
            expected_results=["Expected result 1"],
            coverage="covered",
        )


@pytest.mark.parametrize("coverage", ["covered", "partially_covered", "blocked"])
def test_vplan_columns_accepts_valid_coverage_values(coverage):
    row = VPlanColumns(
        test_id="TEST_REQ_I2C_001_001",
        requirement_id="REQ_I2C_001",
        test_type="positive",
        test_description="Verify behaviour.",
        test_constraints="None specified",
        test_steps=["Step 1"],
        expected_results=["Expected result 1"],
        coverage=coverage,
    )

    assert row.coverage == coverage


def test_vplan_columns_rejects_invalid_coverage_value():
    with pytest.raises(ValidationError):
        VPlanColumns(
            test_id="TEST_REQ_I2C_001_001",
            requirement_id="REQ_I2C_001",
            test_type="positive",
            test_description="Verify behaviour.",
            test_constraints="None specified",
            test_steps=["Step 1"],
            expected_results=["Expected result 1"],
            coverage="not_covered",
        )


def test_vplan_columns_requires_all_fields():
    with pytest.raises(ValidationError):
        VPlanColumns(
            test_id="TEST_REQ_I2C_001_001",
            requirement_id="REQ_I2C_001",
            test_type="positive",
            test_description="Verify behaviour.",
            test_constraints="None specified",
            test_steps=["Step 1"],
        )


def test_vplan_columns_rejects_non_list_test_steps():
    with pytest.raises(ValidationError):
        VPlanColumns(
            test_id="TEST_REQ_I2C_001_001",
            requirement_id="REQ_I2C_001",
            test_type="positive",
            test_description="Verify behaviour.",
            test_constraints="None specified",
            test_steps="Step 1",
            expected_results=["Expected result 1"],
            coverage="covered",
        )


def test_vplan_columns_rejects_non_list_expected_results():
    with pytest.raises(ValidationError):
        VPlanColumns(
            test_id="TEST_REQ_I2C_001_001",
            requirement_id="REQ_I2C_001",
            test_type="positive",
            test_description="Verify behaviour.",
            test_constraints="None specified",
            test_steps=["Step 1"],
            expected_results="Expected result 1",
            coverage="covered",
        )


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


def test_table_accepts_valid_vplan_rows():
    row = VPlanColumns(
        test_id="TEST_REQ_I2C_001_001",
        requirement_id="REQ_I2C_001",
        test_type="positive",
        test_description="Verify behaviour.",
        test_constraints="None specified",
        test_steps=["Step 1"],
        expected_results=["Expected result 1"],
        coverage="covered",
    )

    table = Table(feature_list=[row])

    assert len(table.feature_list) == 1
    assert table.feature_list[0].test_id == "TEST_REQ_I2C_001_001"


def test_table_accepts_dict_rows_and_converts_to_models():
    table = Table(
        feature_list=[
            {
                "test_id": "TEST_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
                "test_type": "positive",
                "test_description": "Verify behaviour.",
                "test_constraints": "None specified",
                "test_steps": ["Step 1"],
                "expected_results": ["Expected result 1"],
                "coverage": "covered",
            }
        ]
    )

    assert isinstance(table.feature_list[0], VPlanColumns)


def test_table_rejects_invalid_row():
    with pytest.raises(ValidationError):
        Table(
            feature_list=[
                {
                    "test_id": "TEST_REQ_I2C_001_001",
                    "requirement_id": "REQ_I2C_001",
                    "test_type": "invalid",
                    "test_description": "Verify behaviour.",
                    "test_constraints": "None specified",
                    "test_steps": ["Step 1"],
                    "expected_results": ["Expected result 1"],
                    "coverage": "covered",
                }
            ]
        )


# ---------------------------------------------------------------------------
# EdgeCaseCandidate
# ---------------------------------------------------------------------------


def test_edge_case_candidate_accepts_valid_data():
    edge_case = EdgeCaseCandidate(
        edge_case_id="EDGE_REQ_I2C_001_001",
        requirement_id="REQ_I2C_001",
        edge_case_type="optional_behaviour",
        edge_case_description="Fast-mode support may be optional.",
    )

    assert edge_case.edge_case_id == "EDGE_REQ_I2C_001_001"
    assert edge_case.requirement_id == "REQ_I2C_001"
    assert edge_case.edge_case_type == "optional_behaviour"


@pytest.mark.parametrize(
    "edge_case_type",
    [
        "optional_behaviour",
        "conditional_behaviour",
        "ambiguous_expected_result",
        "unclear_mandatory_status",
        "implementation_dependent",
        "timing_or_ordering_edge_case",
        "boundary_condition",
    ],
)
def test_edge_case_candidate_accepts_valid_edge_case_types(edge_case_type):
    edge_case = EdgeCaseCandidate(
        edge_case_id="EDGE_REQ_I2C_001_001",
        requirement_id="REQ_I2C_001",
        edge_case_type=edge_case_type,
        edge_case_description="Example edge case.",
    )

    assert edge_case.edge_case_type == edge_case_type


def test_edge_case_candidate_rejects_invalid_edge_case_type():
    with pytest.raises(ValidationError):
        EdgeCaseCandidate(
            edge_case_id="EDGE_REQ_I2C_001_001",
            requirement_id="REQ_I2C_001",
            edge_case_type="invalid_type",
            edge_case_description="Example edge case.",
        )


def test_edge_case_candidate_requires_all_fields():
    with pytest.raises(ValidationError):
        EdgeCaseCandidate(
            edge_case_id="EDGE_REQ_I2C_001_001",
            requirement_id="REQ_I2C_001",
            edge_case_type="optional_behaviour",
        )


# ---------------------------------------------------------------------------
# EdgeCaseCandidateList
# ---------------------------------------------------------------------------


def test_edge_case_candidate_list_accepts_valid_edge_cases():
    edge_cases = EdgeCaseCandidateList(
        edge_cases=[
            {
                "edge_case_id": "EDGE_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
                "edge_case_type": "optional_behaviour",
                "edge_case_description": "Fast-mode support may be optional.",
            }
        ]
    )

    assert len(edge_cases.edge_cases) == 1
    assert isinstance(edge_cases.edge_cases[0], EdgeCaseCandidate)


def test_edge_case_candidate_list_rejects_invalid_edge_case():
    with pytest.raises(ValidationError):
        EdgeCaseCandidateList(
            edge_cases=[
                {
                    "edge_case_id": "EDGE_REQ_I2C_001_001",
                    "requirement_id": "REQ_I2C_001",
                    "edge_case_type": "invalid_type",
                    "edge_case_description": "Example edge case.",
                }
            ]
        )


# ---------------------------------------------------------------------------
# CoverageFinding
# ---------------------------------------------------------------------------


def test_coverage_finding_accepts_valid_data():
    finding = CoverageFinding(
        requirement_id="REQ_I2C_001",
        requirement_text="The controller shall operate at 100 Kbps.",
        coverage_status="covered",
        matched_test_ids=["TEST_REQ_I2C_001_001"],
        covered_behaviours=["Normal-mode operation"],
        missing_behaviours=[],
        reasoning="The vPlan includes a relevant test.",
        suggested_action="No action needed.",
    )

    assert finding.requirement_id == "REQ_I2C_001"
    assert finding.coverage_status == "covered"
    assert finding.matched_test_ids == ["TEST_REQ_I2C_001_001"]


@pytest.mark.parametrize(
    "coverage_status",
    ["covered", "partially_covered", "not_covered", "blocked"],
)
def test_coverage_finding_accepts_valid_coverage_statuses(coverage_status):
    finding = CoverageFinding(
        requirement_id="REQ_I2C_001",
        requirement_text="Requirement text.",
        coverage_status=coverage_status,
        matched_test_ids=[],
        covered_behaviours=[],
        missing_behaviours=[],
        reasoning="Example reasoning.",
        suggested_action="Example action.",
    )

    assert finding.coverage_status == coverage_status


def test_coverage_finding_rejects_invalid_coverage_status():
    with pytest.raises(ValidationError):
        CoverageFinding(
            requirement_id="REQ_I2C_001",
            requirement_text="Requirement text.",
            coverage_status="invalid",
            matched_test_ids=[],
            covered_behaviours=[],
            missing_behaviours=[],
            reasoning="Example reasoning.",
            suggested_action="Example action.",
        )


def test_coverage_finding_rejects_non_list_matched_test_ids():
    with pytest.raises(ValidationError):
        CoverageFinding(
            requirement_id="REQ_I2C_001",
            requirement_text="Requirement text.",
            coverage_status="covered",
            matched_test_ids="TEST_REQ_I2C_001_001",
            covered_behaviours=[],
            missing_behaviours=[],
            reasoning="Example reasoning.",
            suggested_action="Example action.",
        )


def test_coverage_finding_requires_all_fields():
    with pytest.raises(ValidationError):
        CoverageFinding(
            requirement_id="REQ_I2C_001",
            requirement_text="Requirement text.",
            coverage_status="covered",
            matched_test_ids=[],
        )


# ---------------------------------------------------------------------------
# CoverageSummary
# ---------------------------------------------------------------------------


def test_coverage_summary_accepts_valid_data():
    summary = CoverageSummary(
        total_requirements=4,
        covered_count=2,
        partially_covered_count=1,
        not_covered_count=1,
        blocked_count=0,
        coverage_percentage=50.0,
    )

    assert summary.total_requirements == 4
    assert summary.covered_count == 2
    assert summary.coverage_percentage == 50.0


def test_coverage_summary_rejects_missing_fields():
    with pytest.raises(ValidationError):
        CoverageSummary(
            total_requirements=4,
            covered_count=2,
            partially_covered_count=1,
        )


def test_coverage_summary_coerces_numeric_strings_current_pydantic_behaviour():
    summary = CoverageSummary(
        total_requirements="4",
        covered_count="2",
        partially_covered_count="1",
        not_covered_count="1",
        blocked_count="0",
        coverage_percentage="50.0",
    )

    assert summary.total_requirements == 4
    assert summary.coverage_percentage == 50.0


# ---------------------------------------------------------------------------
# CoverageReport
# ---------------------------------------------------------------------------


def test_coverage_report_accepts_valid_data():
    report = CoverageReport(
        summary={
            "total_requirements": 1,
            "covered_count": 1,
            "partially_covered_count": 0,
            "not_covered_count": 0,
            "blocked_count": 0,
            "coverage_percentage": 100.0,
        },
        findings=[
            {
                "requirement_id": "REQ_I2C_001",
                "requirement_text": "Requirement text.",
                "coverage_status": "covered",
                "matched_test_ids": ["TEST_REQ_I2C_001_001"],
                "covered_behaviours": ["Behaviour covered."],
                "missing_behaviours": [],
                "reasoning": "The test matches the requirement.",
                "suggested_action": "No action needed.",
            }
        ],
    )

    assert isinstance(report.summary, CoverageSummary)
    assert isinstance(report.findings[0], CoverageFinding)


def test_coverage_report_rejects_invalid_summary():
    with pytest.raises(ValidationError):
        CoverageReport(
            summary={
                "total_requirements": 1,
            },
            findings=[],
        )


def test_coverage_report_rejects_invalid_finding():
    with pytest.raises(ValidationError):
        CoverageReport(
            summary={
                "total_requirements": 1,
                "covered_count": 1,
                "partially_covered_count": 0,
                "not_covered_count": 0,
                "blocked_count": 0,
                "coverage_percentage": 100.0,
            },
            findings=[
                {
                    "requirement_id": "REQ_I2C_001",
                    "requirement_text": "Requirement text.",
                    "coverage_status": "invalid",
                    "matched_test_ids": [],
                    "covered_behaviours": [],
                    "missing_behaviours": [],
                    "reasoning": "Example reasoning.",
                    "suggested_action": "Example action.",
                }
            ],
        )


# ---------------------------------------------------------------------------
# TypedDict runtime behaviour
# ---------------------------------------------------------------------------


def test_graph_state_can_be_created_as_plain_dict():
    state: GraphState = {
        "requirements_file": "example-requirements.json",
    }

    assert state["requirements_file"] == "example-requirements.json"


def test_graph_state_accepts_optional_keys():
    state: GraphState = {
        "requirements_file": "example-requirements.json",
        "vplan": {"feature_list": []},
        "edge_cases": {"edge_cases": []},
        "vplan_output_file": "generated-vplan.json",
        "edge_case_output_file": "generated-edge-cases.json",
        "requirement_test_links_file": "links.csv",
        "vplan_usage": {"total_tokens": 100},
        "edge_case_usage": {"total_tokens": 50},
        "vplan_trace_id": "trace-vplan",
        "edge_case_trace_id": "trace-edge",
        "langsmith_summary": {"total_cost": 0.01},
        "langsmith_log_file": "langsmith.json",
        "usage_reports": {"summary": {}},
        "blocked_test_report_file": "blocked-report.json",
    }

    assert state["vplan"]["feature_list"] == []
    assert state["blocked_test_report_file"] == "blocked-report.json"


def test_coverage_graph_state_can_be_created_as_plain_dict():
    state: CoverageGraphState = {
        "requirements_file": "example-requirements.json",
        "vplan_file": "generated-vplan.json",
    }

    assert state["requirements_file"] == "example-requirements.json"
    assert state["vplan_file"] == "generated-vplan.json"


def test_coverage_graph_state_accepts_optional_keys():
    state: CoverageGraphState = {
        "requirements_file": "example-requirements.json",
        "vplan_file": "generated-vplan.json",
        "coverage_report": {"summary": {}},
        "coverage_output_file": "coverage-report.json",
        "coverage_validation_errors": ["Missing requirement"],
        "coverage_missing_requirement_ids": ["REQ_I2C_999"],
    }

    assert state["coverage_output_file"] == "coverage-report.json"
    assert state["coverage_missing_requirement_ids"] == ["REQ_I2C_999"]
