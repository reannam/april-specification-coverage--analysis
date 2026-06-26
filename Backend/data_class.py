from langgraph.store.base import Result
from pydantic import BaseModel, Field
from typing import Literal, TypedDict, NotRequired, Any

class VPlanColumns(BaseModel):
    test_id: str = Field(..., description="Unique test ID, e.g. TEST_REQ_I2C_001")
    requirement_id: str = Field(..., description="The exact requirement ID from the input JSON")
    test_type: Literal["positive", "negative"] = Field(..., description="The type of test")
    test_description: str = Field(..., description="What is being tested")
    test_constraints: str = Field(..., description="Constraints, preconditions, or 'None specified'")
    test_steps: list[str] = Field(..., description="Concrete verification steps")
    expected_results: list[str] = Field(..., description="Expected observable results")
    priority: Literal[1, 2, 3] = Field(..., description="1 = high, 2 = medium, 3 = low")
    coverage: Literal["covered", "partially_covered", "blocked"] = Field(
        ...,
        description="Coverage status of the requirement",
    )


class Table(BaseModel):
    feature_list: list[VPlanColumns] = Field(..., description="Rows of vPlan table")


class EdgeCaseCandidate(BaseModel):
    edge_case_id: str = Field(..., description="Unique edge-case ID, e.g. EDGE_REQ_I2C_001")
    requirement_id: str = Field(..., description="The exact requirement ID from the input JSON" )
    edge_case_type: Literal[
        "optional_behaviour",
        "conditional_behaviour",
        "ambiguous_expected_result",
        "unclear_mandatory_status",
        "implementation_dependent",
        "timing_or_ordering_edge_case",
        "boundary_condition",
    ] = Field(..., description="The type of edge case identified.")
    edge_case_description: str = Field(
        ...,
        description="Concise description of the edge case implied by the requirement wording. "
                    "Reference what makes this particular requirement an edge-case",
    )

class EdgeCaseCandidateList(BaseModel):
    edge_cases: list[EdgeCaseCandidate] = Field(
        ...,
        description="List of edge-case candidates extracted from weak or ambiguous requirements.",
    )


class GraphState(TypedDict):
    requirements_file: str

    vplan: NotRequired[dict[str, Any]]
    vplan_output_file: NotRequired[str]
    vplan_trace_id: NotRequired[str]
    vplan_usage: NotRequired[dict[str, Any]]

    edge_cases: NotRequired[dict[str, Any]]
    edge_case_output_file: NotRequired[str]
    edge_case_trace_id: NotRequired[str]
    edge_case_usage: NotRequired[dict[str, Any]]

    langsmith_log_file: NotRequired[str]
    langsmith_summary: NotRequired[dict[str, Any]]
    usage_reports: NotRequired[dict[str, str]]