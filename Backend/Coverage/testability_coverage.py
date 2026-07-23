from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain.agents import create_agent

from Backend.Coverage.batched_model_review import run_review_batches
from Backend.Coverage.related_requirements import (
    index_requirements,
    resolve_supporting_requirements,
)

load_dotenv()


class TestabilityAssessment(BaseModel):
    requirement_id: str = Field(..., description="Requirement ID being assessed.")
    testability_label: Literal[
        "fully_testable",
        "partially_testable",
        "not_testable",
        "not_mapped",
        "unclear",
    ] = Field(..., description="Testability classification.")
    is_testable: bool = Field(
        ...,
        description="True if the mapped vPlan entry is clear enough to verify.",
    )
    reason: str = Field(
        ..., description="Brief explanation of the testability judgement."
    )
    linked_tests: list[str] = Field(default_factory=list)


class TestabilityAssessmentList(BaseModel):
    assessments: list[TestabilityAssessment]


TESTABILITY_PROMPT = """
You are a verification testability reviewer.

You are given one or more assessment_items. Each contains:
- One extracted specification requirement.
- The vPlan items linked to that requirement.
- Zero or more supporting_requirements explicitly cited by those vPlan items.

Supporting-requirement rules:
- Use a supporting requirement only when its supplied text directly defines a value,
  condition, signal, outcome, or rule needed by the primary requirement.
- Do not improve testability because a supporting requirement is merely similar or shares
  a category.
- Do not use uncited requirements or outside engineering knowledge.
- If the cited material still leaves a gap, retain the stricter result.

Your task is to decide whether the mapped vPlan item is clear enough to verify.

A strong testable vPlan item should contain:
- feature or behaviour name
- objective
- scenario or condition
- expected outcome

Labels:
- fully_testable:
  The vPlan entry clearly verifies the requirement and includes a concrete expected result.
- partially_testable:
  The vPlan entry mentions the requirement, but is incomplete, vague, missing a condition, or missing a clear expected outcome.
- not_testable:
  A linked vPlan item exists, but it is too generic or not verification-worthy.
- not_mapped:
  No linked vPlan item exists.
- unclear:
  The provided information is insufficient to judge.

Rules:
- Return exactly one assessment for every input requirement_id.
- Copy each requirement_id exactly and do not merge assessments.
- linked_tests must contain every test_id supplied for that requirement exactly once.
- Never omit a linked test because it is uncovered, incomplete, or untestable; record it
  in linked_tests and reflect its quality in the label and reason.
- Only use the provided requirement and linked vPlan items.
- Do not invent missing test detail.
- Be strict.
- A row marked uncovered is a traceability record, not a test, and must be classified
  not_testable unless another linked row contains a real supported test.
- A row with an empty description, no executable steps, or no observable expected
  results is not fully testable.
- Partially testable requires at least one concrete, requirement-supported action and
  at least one observable expected result. Otherwise use not_testable.
- Do not trust the vPlan coverage label by itself; judge the actual test content against
  the provided requirement.
- Never infer signals, values, timing, configuration, stimulus, or outcomes that the
  requirement does not provide.
- When evidence is borderline, choose partially_testable or not_testable rather than
  fully_testable.
- Generic tests such as "verify protocol correctness" are not fully testable.
- A test with steps but no clear expected outcome is only partially testable.
- A test with a clear condition and expected result can be fully testable.
"""


_agent = None
TESTABILITY_MODEL = os.getenv(
    "TESTABILITY_MODEL",
    "openai:gpt-5.4",
)


def get_agent():
    global _agent

    if _agent is None:
        _agent = create_agent(
            model=TESTABILITY_MODEL,
            system_prompt=TESTABILITY_PROMPT,
            response_format=TestabilityAssessmentList,
        )

    return _agent


def load_json(file_path: str | Path) -> dict[str, Any] | list[dict[str, Any]]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_spec_requirements(spec_data: dict[str, Any]) -> list[dict[str, Any]]:
    requirements = spec_data.get("requirements", [])

    if not isinstance(requirements, list):
        raise ValueError("Spec JSON must contain a top-level 'requirements' list.")

    return requirements


def extract_vplan_items(
    vplan_data: dict[str, Any] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(vplan_data, list):
        return vplan_data

    if isinstance(vplan_data.get("feature_list"), list):
        return vplan_data["feature_list"]

    if isinstance(vplan_data.get("table"), dict):
        feature_list = vplan_data["table"].get("feature_list")
        if isinstance(feature_list, list):
            return feature_list

    if isinstance(vplan_data.get("vplan"), list):
        return vplan_data["vplan"]

    raise ValueError(
        "Could not find vPlan items. Expected 'feature_list', 'table.feature_list', or 'vplan'."
    )


def get_requirement_id(item: dict[str, Any]) -> str | None:
    requirement_id = item.get("requirement_id") or item.get("id")

    if requirement_id is None:
        return None

    return str(requirement_id)


def get_test_id(vplan_item: dict[str, Any], fallback_index: int) -> str:
    return str(
        vplan_item.get("test_id")
        or vplan_item.get("id")
        or f"VPLAN_ITEM_{fallback_index + 1:03d}"
    )


def group_vplan_items_by_requirement_id(
    vplan_items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for item in vplan_items:
        requirement_id = get_requirement_id(item)

        if requirement_id is None:
            continue

        grouped.setdefault(requirement_id, []).append(item)

    return grouped


def build_requirement_payload(
    requirement: dict[str, Any],
    linked_vplan_items: list[dict[str, Any]],
    requirements_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    simplified_tests = []

    for index, item in enumerate(linked_vplan_items):
        simplified_tests.append(
            {
                "test_id": get_test_id(item, index),
                "requirement_id": item.get("requirement_id"),
                "supporting_requirement_ids": item.get(
                    "supporting_requirement_ids", []
                ),
                "requirement_text": item.get("requirement_text"),
                "test_description": item.get("test_description"),
                "test_constraints": item.get("test_constraints"),
                "test_steps": item.get("test_steps"),
                "expected_results": item.get("expected_results"),
                "coverage": item.get("coverage"),
            }
        )

    requirement_id = str(requirement.get("id"))
    return {
        "requirement": {
            "id": requirement.get("id"),
            "text": requirement.get("text"),
            "source_section": requirement.get("source_section"),
            "signals": requirement.get("signals", []),
            "type": requirement.get("type"),
        },
        "supporting_requirements": resolve_supporting_requirements(
            requirement_id,
            linked_vplan_items,
            requirements_by_id or {},
        ),
        "linked_vplan_items": simplified_tests,
    }


def assess_requirement_testability(
    requirement: dict[str, Any],
    linked_vplan_items: list[dict[str, Any]],
) -> TestabilityAssessment:
    requirement_id = get_requirement_id(requirement)

    if requirement_id is None:
        return TestabilityAssessment(
            requirement_id="UNKNOWN_REQUIREMENT_ID",
            testability_label="unclear",
            is_testable=False,
            reason="Requirement does not have an ID.",
            linked_tests=[],
        )

    if not linked_vplan_items:
        return TestabilityAssessment(
            requirement_id=requirement_id,
            testability_label="not_mapped",
            is_testable=False,
            reason=(
                "No linked vPlan item exists for this requirement. "
                f"Requirement text: {requirement.get('text')}"
            ),
            linked_tests=[],
        )

    payload = build_requirement_payload(requirement, linked_vplan_items)

    response = get_agent().invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(payload, indent=2),
                }
            ]
        }
    )

    structured_response = response["structured_response"]

    if not structured_response.assessments:
        return TestabilityAssessment(
            requirement_id=requirement_id,
            testability_label="unclear",
            is_testable=False,
            reason="Agent returned no assessment.",
            linked_tests=[
                get_test_id(item, index)
                for index, item in enumerate(linked_vplan_items)
            ],
        )

    return structured_response.assessments[0]


def calculate_testability_coverage(
    spec_requirements: list[dict[str, Any]],
    vplan_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Testability coverage =
        mapped requirements with testable vPlan entry
        / mapped spec items
        * 100
    """

    vplan_by_requirement_id = group_vplan_items_by_requirement_id(vplan_items)
    requirements_by_id = index_requirements(spec_requirements)

    assessment_payloads = []
    linked_items_by_id: dict[str, list[dict[str, Any]]] = {}
    assessments_by_id: dict[str, TestabilityAssessment] = {}

    for requirement in spec_requirements:
        requirement_id = get_requirement_id(requirement)
        if requirement_id is None:
            continue

        linked_vplan_items = vplan_by_requirement_id.get(requirement_id, [])
        linked_items_by_id[requirement_id] = linked_vplan_items

        if not linked_vplan_items:
            assessments_by_id[requirement_id] = TestabilityAssessment(
                requirement_id=requirement_id,
                testability_label="not_mapped",
                is_testable=False,
                reason="No linked vPlan item exists for this requirement.",
                linked_tests=[],
            )
        else:
            assessment_payloads.append(
                build_requirement_payload(
                    requirement, linked_vplan_items, requirements_by_id
                )
            )

    model_assessments, usage = run_review_batches(
        review_name="testability_coverage",
        model_name=TESTABILITY_MODEL.removeprefix("openai:"),
        payloads=assessment_payloads,
        get_agent=get_agent,
    )

    expected_model_ids = {
        str(payload["requirement"]["id"]) for payload in assessment_payloads
    }
    for assessment in model_assessments:
        if assessment.requirement_id in expected_model_ids:
            if assessment.testability_label == "not_mapped" and linked_items_by_id.get(
                assessment.requirement_id
            ):
                assessment = assessment.model_copy(
                    update={
                        "is_testable": False,
                        "testability_label": "unclear",
                        "reason": (
                            "Linked vPlan items exist, so this requirement is mapped; "
                            "the model returned an inconsistent not_mapped label."
                        ),
                    }
                )
            assessments_by_id.setdefault(assessment.requirement_id, assessment)

    assessments = []
    for requirement in spec_requirements:
        requirement_id = get_requirement_id(requirement)
        if requirement_id is None:
            assessment = TestabilityAssessment(
                requirement_id="UNKNOWN_REQUIREMENT_ID",
                testability_label="unclear",
                is_testable=False,
                reason="Requirement does not have an ID.",
                linked_tests=[],
            )
        else:
            assessment = assessments_by_id.get(requirement_id)
            if assessment is None:
                linked_items = linked_items_by_id.get(requirement_id, [])
                assessment = TestabilityAssessment(
                    requirement_id=requirement_id,
                    testability_label="unclear",
                    is_testable=False,
                    reason="No valid assessment was returned for this requirement.",
                    linked_tests=[
                        get_test_id(item, index)
                        for index, item in enumerate(linked_items)
                    ],
                )

        assessment_data = assessment.model_dump()
        assessment_data["requirement_text"] = (
            requirement.get("text") or requirement.get("description") or ""
        )
        assessment_data["source_section"] = requirement.get(
            "source_section"
        ) or requirement.get("section")
        assessment_data["supporting_requirements"] = (
            resolve_supporting_requirements(
                str(requirement_id),
                linked_items_by_id.get(str(requirement_id), []),
                requirements_by_id,
            )
            if requirement_id is not None
            else []
        )
        assessments.append(assessment_data)

    mapped_assessments = [
        assessment
        for assessment in assessments
        if assessment["testability_label"] != "not_mapped"
    ]

    testable_assessments = [
        assessment
        for assessment in mapped_assessments
        if assessment["is_testable"] is True
    ]

    mapped_spec_items = len(mapped_assessments)
    testable_items = len(testable_assessments)

    testability_coverage = (
        round((testable_items / mapped_spec_items) * 100, 2)
        if mapped_spec_items > 0
        else 0.0
    )

    label_counts: dict[str, int] = {}

    for assessment in assessments:
        label = assessment["testability_label"]
        label_counts[label] = label_counts.get(label, 0) + 1

    return {
        "metric_name": "Testability Coverage",
        "definition": (
            "Percentage of mapped requirements that are written in a form clear enough to verify."
        ),
        "formula": "(mapped_items_with_testable_vplan_entry / mapped_spec_items) * 100",
        "total_requirements": len(spec_requirements),
        "mapped_spec_items": mapped_spec_items,
        "mapped_items_with_testable_vplan_entry": testable_items,
        "mapped_items_without_testable_vplan_entry": mapped_spec_items - testable_items,
        "requirements_not_mapped": label_counts.get("not_mapped", 0),
        "testability_coverage": testability_coverage,
        "label_counts": label_counts,
        "assessments": assessments,
        "vplan_item_audit": {
            "total_vplan_items": len(vplan_items),
            "vplan_items_submitted_to_model": usage.get("vplan_items_submitted", 0),
            "test_ids_submitted_to_model": usage.get("test_ids_submitted", []),
            "failed_requirement_ids": usage.get("failed_requirement_ids", []),
            "quota_exhausted": usage.get("quota_exhausted", False),
        },
        "usage": usage,
    }


def run_testability_coverage(
    spec_file: str | Path,
    vplan_file: str | Path,
) -> dict[str, Any]:
    spec_data = load_json(spec_file)
    vplan_data = load_json(vplan_file)

    if not isinstance(spec_data, dict):
        raise ValueError("Spec file must contain a JSON object.")

    spec_requirements = extract_spec_requirements(spec_data)
    vplan_items = extract_vplan_items(vplan_data)

    return calculate_testability_coverage(
        spec_requirements=spec_requirements,
        vplan_items=vplan_items,
    )


def print_testability_coverage_summary(result: dict[str, Any]) -> None:
    print("\nTestability Coverage")
    print("--------------------")
    print(f"Total requirements:                         {result['total_requirements']}")
    print(f"Mapped spec items:                          {result['mapped_spec_items']}")
    print(
        "Mapped items with testable vPlan entry:     "
        f"{result['mapped_items_with_testable_vplan_entry']}"
    )
    print(
        "Mapped items without testable entry:        "
        f"{result['mapped_items_without_testable_vplan_entry']}"
    )
    print(
        f"Requirements not mapped:                    {result['requirements_not_mapped']}"
    )
    print(
        f"Testability coverage:                       {result['testability_coverage']}%"
    )

    print("\nLabel counts:")
    for label, count in result["label_counts"].items():
        print(f"  - {label}: {count}")

    not_testable = [
        assessment
        for assessment in result["assessments"]
        if assessment["testability_label"]
        in {"not_testable", "partially_testable", "unclear"}
    ]

    if not_testable:
        print("\nMapped requirements without fully testable vPlan entries:")
        for assessment in not_testable:
            print(
                f"  - {assessment['requirement_id']} ({assessment['testability_label']}): {assessment['reason']}"
            )

    not_mapped = [
        assessment
        for assessment in result["assessments"]
        if assessment["testability_label"] == "not_mapped"
    ]

    if not_mapped:
        print("\nRequirements not mapped:")
        for assessment in not_mapped:
            print(f"  - {assessment['requirement_id']}: {assessment['reason']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate agent-assisted testability coverage."
    )

    parser.add_argument(
        "--spec-file",
        required=True,
        help="Path to the extracted spec JSON file.",
    )

    parser.add_argument(
        "--vplan-file",
        required=True,
        help="Path to the generated vPlan JSON file.",
    )

    args = parser.parse_args()

    result = run_testability_coverage(
        spec_file=args.spec_file,
        vplan_file=args.vplan_file,
    )

    print_testability_coverage_summary(result)
