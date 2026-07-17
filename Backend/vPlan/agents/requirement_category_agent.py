"""Create one controlled requirement taxonomy before vPlan generation."""

from __future__ import annotations

import json
from pathlib import Path
import uuid

from langchain.agents import create_agent
from langchain_community.callbacks.manager import get_openai_callback
from langchain_openai import ChatOpenAI

from Backend.config import (
    REQUIREMENT_CATEGORY_BATCH_RETRIES,
    REQUIREMENT_CATEGORY_BATCH_SIZE,
    REQUIREMENT_CATEGORY_MODEL,
)
from Backend.vPlan.agents.vplan_generator_utils import chunk_requirements, combine_usage
from Backend.vPlan.post_processing.usage_logger import normalise_usage
from Backend.vPlan.pre_processing.data_class import (
    RequirementCategoryAssignments,
    RequirementTaxonomy,
)
from Backend.vPlan.report_generation.weak_language_check import unwrap_requirements

TAXONOMY_PROMPT = """You organise engineering requirements for verification planning.

Read the complete supplied specification and define one reusable hierarchy.

Rules:
- Produce 6 to 12 broad parent categories unless the input is too small to justify six.
- Prefer merging related concerns into one parent category over creating similar parents.
- Each parent must contain useful, mutually distinguishable subcategories.
- Use 2 to 8 subcategories per parent where the material supports them.
- Categories and subcategories are organisational labels, not new requirements.
- Use concise engineering nouns. Avoid General, Other, Miscellaneous, Functional,
  Verification, chapter names, and requirement IDs.
- Base the hierarchy only on concepts present in the supplied requirements.
- Do not assign individual requirements in this response.
"""


ASSIGNMENT_PROMPT = """Assign every supplied requirement to the fixed taxonomy.

Rules:
- Return exactly one assignment for every supplied requirement_id.
- category must exactly match a supplied parent category.
- subcategory must exactly match one subcategory belonging to that parent.
- Reuse the closest slightly related parent rather than inventing a new label.
- Do not modify IDs or create categories and subcategories.
"""


def create_category_model() -> ChatOpenAI:
    """Create a Chat Completions model compatible with schema-tool output.

    GPT-5.6 Chat Completions rejects function tools when reasoning is enabled.
    The categoriser uses a Pydantic response schema, which LangChain implements
    through such a tool, so reasoning must be disabled for these calls.
    """

    return ChatOpenAI(
        model=REQUIREMENT_CATEGORY_MODEL.removeprefix("openai:"),
        reasoning_effort="none",
    )


def _usage(callback, agent_name: str) -> dict:
    return normalise_usage(
        agent_name=agent_name,
        input_tokens=callback.prompt_tokens,
        output_tokens=callback.completion_tokens,
        total_tokens=callback.total_tokens,
        total_cost=callback.total_cost,
        model_name=REQUIREMENT_CATEGORY_MODEL.removeprefix("openai:"),
    )


def _requirement_payload(requirement: dict) -> dict:
    """Keep taxonomy context useful without forwarding unrelated extractor fields."""

    return {
        "requirement_id": requirement.get("id"),
        "text": requirement.get("text") or requirement.get("requirement_text") or "",
        "type": requirement.get("type"),
        "source_section": requirement.get("source_section")
        or requirement.get("section")
        or requirement.get("chapter"),
    }


def _invoke_taxonomy(requirements: list[dict]) -> tuple[RequirementTaxonomy, dict, str]:
    agent = create_agent(
        model=create_category_model(),
        response_format=RequirementTaxonomy,
        system_prompt=TAXONOMY_PROMPT,
    )
    run_id = uuid.uuid4()

    with get_openai_callback() as callback:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Create one taxonomy from this complete specification:\n"
                        + json.dumps(
                            [_requirement_payload(item) for item in requirements],
                            separators=(",", ":"),
                        ),
                    }
                ]
            },
            config={
                "run_id": run_id,
                "run_name": "requirement_taxonomy",
                "metadata": {
                    "requirement_count": len(requirements),
                    "ls_provider": "openai",
                    "ls_model_name": REQUIREMENT_CATEGORY_MODEL.removeprefix("openai:"),
                },
                "tags": ["requirement-categorisation", "whole-spec-taxonomy"],
            },
        )

        return (
            result["structured_response"],
            _usage(callback, "requirement_taxonomy"),
            str(run_id),
        )


def _normalise_taxonomy(taxonomy: RequirementTaxonomy) -> dict[str, set[str]]:
    hierarchy: dict[str, set[str]] = {}

    for definition in taxonomy.categories:
        category = " ".join(definition.category.split())
        subcategories = {" ".join(value.split()) for value in definition.subcategories}

        if category.casefold() in {value.casefold() for value in hierarchy}:
            raise ValueError(f"Duplicate parent category: {category}")
        if len(subcategories) != len(definition.subcategories):
            raise ValueError(f"Duplicate subcategory in parent category: {category}")

        hierarchy[category] = subcategories

    return hierarchy


def _invoke_assignments(
    batch: list[dict],
    taxonomy: RequirementTaxonomy,
    batch_number: int,
    attempt_number: int,
) -> tuple[RequirementCategoryAssignments, dict, str]:
    agent = create_agent(
        model=create_category_model(),
        response_format=RequirementCategoryAssignments,
        system_prompt=ASSIGNMENT_PROMPT,
    )
    run_id = uuid.uuid4()

    with get_openai_callback() as callback:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "taxonomy": taxonomy.model_dump(),
                                "requirements": [
                                    _requirement_payload(item) for item in batch
                                ],
                            },
                            separators=(",", ":"),
                        ),
                    }
                ]
            },
            config={
                "run_id": run_id,
                "run_name": f"requirement_category_batch_{batch_number}",
                "metadata": {
                    "batch_number": batch_number,
                    "batch_size": len(batch),
                    "attempt_number": attempt_number,
                    "ls_provider": "openai",
                    "ls_model_name": REQUIREMENT_CATEGORY_MODEL.removeprefix("openai:"),
                },
                "tags": ["requirement-categorisation", "fixed-taxonomy-assignment"],
            },
        )

        return (
            result["structured_response"],
            _usage(callback, f"requirement_category_batch_{batch_number}"),
            str(run_id),
        )


def _validated_assignments(
    response: RequirementCategoryAssignments,
    batch: list[dict],
    hierarchy: dict[str, set[str]],
) -> dict[str, tuple[str, str]]:
    expected_ids = {str(item.get("id")) for item in batch if item.get("id") is not None}
    returned_ids = {item.requirement_id for item in response.assignments}

    if returned_ids != expected_ids or len(response.assignments) != len(expected_ids):
        raise ValueError(
            "The category response did not return each requirement ID exactly once."
        )

    normalised_parents = {key.casefold(): key for key in hierarchy}
    assignments: dict[str, tuple[str, str]] = {}

    for item in response.assignments:
        parent = normalised_parents.get(item.category.casefold())
        if parent is None:
            raise ValueError(f"Unknown parent category returned: {item.category}")

        normalised_children = {value.casefold(): value for value in hierarchy[parent]}
        child = normalised_children.get(item.subcategory.casefold())
        if child is None:
            raise ValueError(
                f"Unknown subcategory '{item.subcategory}' for parent '{parent}'."
            )

        assignments[item.requirement_id] = (parent, child)

    return assignments


def categorise_requirements(requirements_file: str | Path) -> dict:
    """Derive a whole-spec taxonomy, assign all requirements, and save the result."""

    input_path = Path(requirements_file)
    with input_path.open("r", encoding="utf-8") as file:
        requirements = unwrap_requirements(json.load(file))

    if not requirements:
        raise ValueError(
            "The requirements file contains no requirements to categorise."
        )

    print(
        f"[Requirement categories] Building one whole-spec taxonomy with "
        f"{REQUIREMENT_CATEGORY_MODEL}."
    )
    taxonomy_error: Exception | None = None
    for taxonomy_attempt in range(1, REQUIREMENT_CATEGORY_BATCH_RETRIES + 2):
        try:
            taxonomy, taxonomy_usage, taxonomy_trace_id = _invoke_taxonomy(requirements)
            break
        except Exception as error:
            taxonomy_error = error
            if taxonomy_attempt <= REQUIREMENT_CATEGORY_BATCH_RETRIES:
                print(
                    f"[Requirement categories] Taxonomy attempt {taxonomy_attempt} "
                    f"failed: {error}. Retrying."
                )
    else:
        raise RuntimeError(
            "Whole-spec requirement taxonomy failed after retries: " f"{taxonomy_error}"
        ) from taxonomy_error
    hierarchy = _normalise_taxonomy(taxonomy)
    print(
        f"[Requirement categories] Taxonomy complete: {len(hierarchy)} parent "
        "categories."
    )

    batches = chunk_requirements(requirements, REQUIREMENT_CATEGORY_BATCH_SIZE)
    assignments: dict[str, tuple[str, str]] = {}
    usages = [taxonomy_usage]
    trace_ids = [taxonomy_trace_id]
    failed_batches: list[int] = []

    for batch_number, batch in enumerate(batches, start=1):
        print(
            f"[Requirement category batch {batch_number}/{len(batches)}] "
            f"Starting {len(batch)} requirements."
        )
        last_error: Exception | None = None

        for attempt in range(1, REQUIREMENT_CATEGORY_BATCH_RETRIES + 2):
            try:
                response, usage, trace_id = _invoke_assignments(
                    batch, taxonomy, batch_number, attempt
                )
                assignments.update(_validated_assignments(response, batch, hierarchy))
                usages.append(usage)
                trace_ids.append(trace_id)
                print(
                    f"[Requirement category batch {batch_number}/{len(batches)}] "
                    "Completed."
                )
                break
            except Exception as error:
                last_error = error
                if attempt <= REQUIREMENT_CATEGORY_BATCH_RETRIES:
                    print(
                        f"[Requirement category batch {batch_number}/{len(batches)}] "
                        f"Attempt {attempt} failed: {error}. Retrying."
                    )
        else:
            failed_batches.append(batch_number)
            print(
                f"[Requirement category batch {batch_number}/{len(batches)}] "
                f"Failed after retries: {last_error}. Continuing as Uncategorised."
            )

    enriched = []
    for requirement in requirements:
        item = dict(requirement)
        category, subcategory = assignments.get(
            str(item.get("id")), ("Uncategorised", "Uncategorised")
        )
        item["requirement_category"] = category
        item["requirement_subcategory"] = subcategory
        enriched.append(item)

    output_path = input_path.with_name(f"{input_path.stem}_categorised.json")
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "metadata": {
                    "requirement_category_model": REQUIREMENT_CATEGORY_MODEL,
                    "taxonomy": taxonomy.model_dump(),
                    "assignment_batch_size": REQUIREMENT_CATEGORY_BATCH_SIZE,
                    "number_of_assignment_batches": len(batches),
                    "failed_assignment_batches": failed_batches,
                },
                "requirements": enriched,
            },
            file,
            indent=2,
            ensure_ascii=False,
        )

    return {
        "requirements_file": str(output_path),
        "categorised_requirements_file": str(output_path),
        "requirement_category_usage": combine_usage(usages),
        "requirement_category_trace_ids": trace_ids,
    }
