from pydantic import BaseModel, Field
from typing import Literal, TypedDict, NotRequired, Any


class VPlanColumns(BaseModel):
    test_id: str = Field(
        ...,
        description="Unique test identifier.",
    )
    requirement_id: str = Field(
        ...,
        description="Exact requirement ID from the input.",
    )
    scenario_type: Literal["nominal", "illegal", "corner"]
    category: str = Field(
        default="Uncategorised",
        description="One or two word engineering category for the test.",
    )
    priority: Literal[1, 2, 3] = Field(
        default=3,
        description="1 is highest priority and 3 is lowest.",
    )
    test_description: str
    test_constraints: str
    test_steps: list[str]
    expected_results: list[str]
    coverage: Literal[
        "covered",
        "partially_covered",
        "blocked",
    ]


class Table(BaseModel):
    feature_list: list[VPlanColumns] = Field(..., description="Rows of vPlan table")


class EdgeCaseCandidate(BaseModel):
    edge_case_id: str = Field(
        ..., description="Unique edge-case ID, e.g. EDGE_REQ_I2C_001"
    )
    requirement_id: str = Field(
        ..., description="The exact requirement ID from the input JSON"
    )
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
        description=(
            "Concise description of the edge case implied by the requirement wording. "
            "Reference what makes this particular requirement an edge-case"
        ),
    )


class EdgeCaseCandidateList(BaseModel):
    edge_cases: list[EdgeCaseCandidate] = Field(
        ...,
        description="List of edge-case candidates extracted from weak or ambiguous requirements.",
    )


class CoverageFinding(BaseModel):
    requirement_id: str = Field(
        ...,
        description="The exact requirement ID from the input JSON.",
    )
    requirement_text: str = Field(
        ...,
        description="The source requirement text or description being assessed.",
    )
    coverage_status: Literal[
        "covered",
        "partially_covered",
        "not_covered",
        "blocked",
    ] = Field(
        ...,
        description="Coverage judgement for this requirement.",
    )
    matched_test_ids: list[str] = Field(
        ...,
        description="vPlan test IDs that meaningfully verify or relate to this requirement.",
    )
    covered_behaviours: list[str] = Field(
        ...,
        description="Specific behaviours from the requirement that are covered by the vPlan.",
    )
    missing_behaviours: list[str] = Field(
        ...,
        description="Specific behaviours from the requirement that are missing or weakly covered.",
    )
    reasoning: str = Field(
        ...,
        description="Concise explanation for the coverage judgement.",
    )
    suggested_action: str = Field(
        ...,
        description="Suggested improvement if coverage is incomplete, otherwise state that no action is needed.",
    )


class CoverageSummary(BaseModel):
    total_requirements: int = Field(
        ..., description="Total number of source requirements assessed."
    )
    covered_count: int = Field(..., description="Number of requirements fully covered.")
    partially_covered_count: int = Field(
        ..., description="Number of requirements partially covered."
    )
    not_covered_count: int = Field(
        ..., description="Number of requirements not covered."
    )
    blocked_count: int = Field(
        ..., description="Number of requirements where coverage could not be assessed."
    )
    coverage_percentage: float = Field(
        ...,
        description="Percentage of requirements fully covered.",
    )


class CoverageReport(BaseModel):
    summary: CoverageSummary = Field(..., description="Overall coverage summary.")
    findings: list[CoverageFinding] = Field(
        ...,
        description="Requirement-by-requirement coverage findings.",
    )


class GraphState(TypedDict):
    requirements_file: str

    original_requirements_file: NotRequired[str]
    preprocessed_requirements_file: NotRequired[str]

    vplan: NotRequired[dict]
    edge_cases: NotRequired[dict]

    vplan_output_file: NotRequired[str]
    edge_case_output_file: NotRequired[str]
    weak_words_file: NotRequired[str]

    requirement_test_links_file: NotRequired[str]

    vplan_usage: NotRequired[dict]
    edge_case_usage: NotRequired[dict]
    category_usage: NotRequired[dict]

    vplan_trace_id: NotRequired[str]
    edge_case_trace_id: NotRequired[str]
    category_trace_id: NotRequired[str | None]

    langsmith_summary: NotRequired[dict]
    langsmith_log_file: NotRequired[str]
    usage_reports: NotRequired[dict]
    blocked_test_report_file: NotRequired[str]


class CoverageGraphState(TypedDict):
    requirements_file: str
    vplan_file: str

    coverage_report: NotRequired[dict[str, Any]]
    coverage_output_file: NotRequired[str]

    coverage_validation_errors: NotRequired[list[str]]
    coverage_missing_requirement_ids: NotRequired[list[str]]


class TestCategory(BaseModel):
    test_id: str
    category: str = Field(
        ...,
        min_length=2,
        max_length=40,
        description="A concise one or two word engineering category.",
    )


class CategorisedTests(BaseModel):
    tests: list[TestCategory]
