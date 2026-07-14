from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain.agents import create_agent
from langchain_community.callbacks.manager import get_openai_callback

from Backend.post_processing.usage_logger import normalise_usage

load_dotenv()


class GranularityAssessment(BaseModel):
    requirement_id: str = Field(..., description="Requirement ID being assessed.")
    suitable_detail: bool = Field(
        ...,
        description="True if the requirement is covered at suitable test detail.",
    )
    granularity_label: Literal[
        "suitable_detail",
        "too_broad",
        "not_mapped",
        "unclear",
    ] = Field(
        ...,
        description="Granularity classification for this requirement.",
    )
    reason: str = Field(
        ...,
        description="Brief explanation of why the mapped vPlan item is suitable or too broad.",
    )
    linked_tests: list[str] = Field(
        default_factory=list,
        description="Test IDs considered for this requirement.",
    )


class GranularityAssessmentList(BaseModel):
    assessments: list[GranularityAssessment]


GRANULARITY_PROMPT = """
You are a verification coverage reviewer.

You are given:
- One extracted specification requirement.
- The vPlan items linked to that requirement.

Your task is to decide whether the requirement is covered at suitable detail.

Definitions:
- suitable_detail:
  The vPlan item clearly and testably addresses this specific requirement.
  It does not hide the requirement inside a vague or generic test.
- too_broad:
  The vPlan item mentions the requirement only as part of a broad/generic test.
  Example: "Verify protocol correctness" for several distinct behaviours.
- not_mapped:
  No linked vPlan item exists.
- unclear:
  The linked vPlan item is too vague to confidently judge.

Rules:
- Do not invent missing tests.
- Only use the provided requirement and linked vPlan items.
- If a requirement has no linked tests, classify it as not_mapped.
- A single vPlan item can be suitable if it is specific enough.
- Multiple requirements sharing one test is not automatically bad, but it is bad if the test is generic or does not clearly verify the individual behaviour.
- Be strict. A vPlan item must describe concrete verification intent to count as suitable detail.
"""


GRANULARITY_MODEL = os.getenv(
    "GRANULARITY_MODEL",
    "openai:gpt-5.4",
)

agent = create_agent(
    model=GRANULARITY_MODEL,
    system_prompt=GRANULARITY_PROMPT,
    response_format=GranularityAssessmentList,
)


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
) -> dict[str, Any]:
    simplified_tests = []

    for index, item in enumerate(linked_vplan_items):
        simplified_tests.append(
            {
                "test_id": get_test_id(item, index),
                "requirement_id": item.get("requirement_id"),
                "test_description": item.get("test_description"),
                "test_constraints": item.get("test_constraints"),
                "test_steps": item.get("test_steps"),
                "expected_results": item.get("expected_results"),
                "coverage": item.get("coverage"),
            }
        )

    return {
        "requirement": {
            "id": requirement.get("id"),
            "text": requirement.get("text"),
            "source_section": requirement.get("source_section"),
            "signals": requirement.get("signals", []),
            "type": requirement.get("type"),
        },
        "linked_vplan_items": simplified_tests,
    }


def assess_requirement_granularity(
    requirement: dict[str, Any],
    linked_vplan_items: list[dict[str, Any]],
) -> GranularityAssessment:
    requirement_id = get_requirement_id(requirement)

    if requirement_id is None:
        return GranularityAssessment(
            requirement_id="UNKNOWN_REQUIREMENT_ID",
            suitable_detail=False,
            granularity_label="unclear",
            reason="Requirement does not have an ID.",
            linked_tests=[],
        )

    if not linked_vplan_items:
        return GranularityAssessment(
            requirement_id=requirement_id,
            suitable_detail=False,
            granularity_label="not_mapped",
            reason=(
                "No linked vPlan item exists for this requirement. "
                f"Requirement text: {requirement.get('text')}"
            ),
            linked_tests=[],
        )

    payload = build_requirement_payload(requirement, linked_vplan_items)

    response = agent.invoke(
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
        return GranularityAssessment(
            requirement_id=requirement_id,
            suitable_detail=False,
            granularity_label="unclear",
            reason="Agent returned no assessment.",
            linked_tests=[
                get_test_id(item, index)
                for index, item in enumerate(linked_vplan_items)
            ],
        )

    return structured_response.assessments[0]


def calculate_granularity_adequacy(
    spec_requirements: list[dict[str, Any]],
    vplan_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Granularity adequacy =
        requirements covered at suitable detail
        / mapped requirements
        * 100
    """

    vplan_by_requirement_id = group_vplan_items_by_requirement_id(vplan_items)

    assessments = []

    with get_openai_callback() as callback:
        for requirement in spec_requirements:
            requirement_id = get_requirement_id(requirement)
            linked_vplan_items = vplan_by_requirement_id.get(
                requirement_id,
                [],
            )

            assessment = assess_requirement_granularity(
                requirement=requirement,
                linked_vplan_items=linked_vplan_items,
            )

            assessment_data = assessment.model_dump()
            assessment_data["requirement_text"] = (
                requirement.get("text") or requirement.get("description") or ""
            )
            assessment_data["source_section"] = requirement.get(
                "source_section"
            ) or requirement.get("section")

            assessments.append(assessment_data)

    usage = normalise_usage(
        agent_name="granularity_adequacy",
        input_tokens=callback.prompt_tokens,
        output_tokens=callback.completion_tokens,
        total_tokens=callback.total_tokens,
        total_cost=callback.total_cost,
        model_name=GRANULARITY_MODEL.removeprefix("openai:"),
    )

    mapped_assessments = [
        assessment
        for assessment in assessments
        if assessment["granularity_label"] != "not_mapped"
    ]

    suitable_detail_assessments = [
        assessment
        for assessment in mapped_assessments
        if assessment["suitable_detail"] is True
    ]

    mapped_requirements_count = len(mapped_assessments)
    suitable_detail_count = len(suitable_detail_assessments)

    granularity_adequacy = (
        round((suitable_detail_count / mapped_requirements_count) * 100, 2)
        if mapped_requirements_count > 0
        else 0.0
    )

    label_counts: dict[str, int] = {}

    for assessment in assessments:
        label = assessment["granularity_label"]
        label_counts[label] = label_counts.get(label, 0) + 1

    return {
        "metric_name": "Granularity Adequacy",
        "definition": (
            "Percentage of mapped requirements that are covered at suitable vPlan detail."
        ),
        "formula": (
            "(requirements_covered_at_suitable_detail / mapped_requirements) * 100"
        ),
        "total_requirements": len(spec_requirements),
        "mapped_requirements": mapped_requirements_count,
        "requirements_covered_at_suitable_detail": suitable_detail_count,
        "requirements_not_mapped": label_counts.get("not_mapped", 0),
        "granularity_adequacy": granularity_adequacy,
        "label_counts": label_counts,
        "assessments": assessments,
        "usage": usage,
    }


def run_granularity_adequacy(
    spec_file: str | Path,
    vplan_file: str | Path,
) -> dict[str, Any]:
    spec_data = load_json(spec_file)
    vplan_data = load_json(vplan_file)

    if not isinstance(spec_data, dict):
        raise ValueError("Spec file must contain a JSON object.")

    spec_requirements = extract_spec_requirements(spec_data)
    vplan_items = extract_vplan_items(vplan_data)

    return calculate_granularity_adequacy(
        spec_requirements=spec_requirements,
        vplan_items=vplan_items,
    )


def print_granularity_adequacy_summary(result: dict[str, Any]) -> None:
    print("\nGranularity Adequacy")
    print("--------------------")
    print(f"Total requirements:                    {result['total_requirements']}")
    print(f"Mapped requirements:                   {result['mapped_requirements']}")
    print(
        "Requirements at suitable detail:       "
        f"{result['requirements_covered_at_suitable_detail']}"
    )
    print(f"Requirements not mapped:               {result['requirements_not_mapped']}")
    print(f"Granularity adequacy:                  {result['granularity_adequacy']}%")

    print("\nLabel counts:")
    for label, count in result["label_counts"].items():
        print(f"  - {label}: {count}")

    not_mapped = [
        assessment
        for assessment in result["assessments"]
        if assessment["granularity_label"] == "not_mapped"
    ]

    if not_mapped:
        print("\nRequirements not mapped:")
        for assessment in not_mapped:
            print(f"  - {assessment['requirement_id']}: {assessment['reason']}")

    too_broad = [
        assessment
        for assessment in result["assessments"]
        if assessment["granularity_label"] == "too_broad"
    ]

    if too_broad:
        print("\nRequirements covered too broadly:")
        for assessment in too_broad:
            print(f"  - {assessment['requirement_id']}: {assessment['reason']}")

    unclear = [
        assessment
        for assessment in result["assessments"]
        if assessment["granularity_label"] == "unclear"
    ]

    if unclear:
        print("\nRequirements with unclear granularity:")
        for assessment in unclear:
            print(f"  - {assessment['requirement_id']}: {assessment['reason']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate agent-assisted granularity adequacy."
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

    result = run_granularity_adequacy(
        spec_file=args.spec_file,
        vplan_file=args.vplan_file,
    )

    print_granularity_adequacy_summary(result)
