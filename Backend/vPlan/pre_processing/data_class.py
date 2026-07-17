from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, TypedDict, NotRequired


class VPlanColumns(BaseModel):
    test_id: str = Field(
        ...,
        description="Unique test identifier.",
    )
    requirement_id: str = Field(
        ...,
        description="Exact requirement ID from the input.",
    )
    requirement_category: str = Field(
        default="Uncategorised",
        description="Source requirement category used to assemble generation batches.",
    )
    requirement_subcategory: str = Field(
        default="Uncategorised",
        description="Finer requirement grouping within requirement_category.",
    )
    supporting_requirement_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Other requirement IDs from the same category batch that explicitly "
            "supply information used by this test."
        ),
    )
    scenario_type: Literal["nominal", "illegal", "corner"] = Field(
        ...,
        description=(
            "Scenario classification only: nominal, illegal, or corner. "
            "Coverage labels do not belong in this field."
        ),
    )
    category: str = Field(
        default="Uncategorised",
        description="One or two word engineering category for the test.",
    )
    priority: Literal[1, 2, 3] = Field(
        default=3,
        description="1 is highest priority and 3 is lowest.",
    )
    test_name: str = Field(
        default="",
        description=(
            "Concise human-readable name derived from the test description. "
            "The enrichment pass fills this field when it is omitted."
        ),
    )
    test_description: str
    test_constraints: str
    test_steps: list[str]
    expected_results: list[str]
    coverage: Literal[
        "covered",
        "partially_covered",
        "uncovered",
    ]

    @model_validator(mode="after")
    def enforce_coverage_content_policy(self):
        """Keep uncovered rows as traceability records, not speculative tests."""

        if self.coverage == "uncovered":
            self.test_name = ""
            self.test_description = ""
            self.test_steps = []
            self.expected_results = []
            return self

        self.test_description = self.test_description.strip()
        self.test_steps = [step.strip() for step in self.test_steps if step.strip()]
        self.expected_results = [
            result.strip() for result in self.expected_results if result.strip()
        ]

        if (
            not self.test_description
            or not self.test_steps
            or not self.expected_results
        ):
            raise ValueError(
                "Covered and partially covered rows require a specific description, "
                "at least one executable step, and at least one expected result. "
                "Use coverage='uncovered' when the requirement does not provide enough "
                "information, and leave those fields empty."
            )

        return self

    @field_validator("scenario_type", mode="before")
    @classmethod
    def normalise_misplaced_coverage_label(cls, value):
        """Prevent one malformed row from aborting an entire generated batch.

        Models occasionally copy the coverage label into scenario_type for an
        uncovered traceability row. Such a row describes the intended normal
        behaviour but lacks enough information to verify it, so nominal is the
        least misleading scenario fallback. Other unknown values still fail
        validation.
        """

        if isinstance(value, str) and value.strip().lower() in {
            "covered",
            "partially_covered",
            "uncovered",
            "not_covered",
        }:
            return "nominal"

        return value


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


class GraphState(TypedDict):
    requirements_file: str

    original_requirements_file: NotRequired[str]
    preprocessed_requirements_file: NotRequired[str]
    categorised_requirements_file: NotRequired[str]

    vplan: NotRequired[dict]
    edge_cases: NotRequired[dict]

    vplan_output_file: NotRequired[str]
    edge_case_output_file: NotRequired[str]
    weak_words_file: NotRequired[str]

    requirement_test_links_file: NotRequired[str]

    vplan_usage: NotRequired[dict]
    edge_case_usage: NotRequired[dict]
    category_usage: NotRequired[dict]
    requirement_category_usage: NotRequired[dict]

    vplan_trace_id: NotRequired[str]
    edge_case_trace_id: NotRequired[str]
    category_trace_id: NotRequired[str | None]
    requirement_category_trace_ids: NotRequired[list[str]]

    langsmith_summary: NotRequired[dict]
    langsmith_log_file: NotRequired[str]
    usage_reports: NotRequired[dict]
    uncovered_test_report_file: NotRequired[str]


class TestCategory(BaseModel):
    test_id: str
    test_name: str = Field(
        default="",
        max_length=80,
        description="A concise name derived from the test description.",
    )
    category: str = Field(
        ...,
        min_length=2,
        max_length=40,
        description="A concise one or two word engineering category.",
    )


class CategorisedTests(BaseModel):
    tests: list[TestCategory]


class RequirementCategoryDefinition(BaseModel):
    category: str = Field(..., min_length=2, max_length=50)
    description: str = Field(..., min_length=2, max_length=240)
    subcategories: list[str] = Field(..., min_length=1, max_length=10)


class RequirementTaxonomy(BaseModel):
    categories: list[RequirementCategoryDefinition] = Field(
        ..., min_length=1, max_length=12
    )


class RequirementCategoryAssignment(BaseModel):
    requirement_id: str
    category: str = Field(..., min_length=2, max_length=50)
    subcategory: str = Field(..., min_length=2, max_length=60)


class RequirementCategoryAssignments(BaseModel):
    assignments: list[RequirementCategoryAssignment]
