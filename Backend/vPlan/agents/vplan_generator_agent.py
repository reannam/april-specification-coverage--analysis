from pathlib import Path
from datetime import datetime
import json
import os
import uuid

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_community.callbacks.manager import get_openai_callback

from Backend.vPlan.pre_processing.data_class import Table
from Backend.vPlan.report_generation.vplan_traceability_check import (
    check_traceability,
    add_requirement_text,
)
from Backend.config import VPLAN_DIR
from Backend.vPlan.post_processing.usage_logger import normalise_usage
from Backend.vPlan.agents.vplan_generator_utils import (
    build_category_batches,
    combine_usage,
    ensure_unique_test_ids,
    filter_edge_cases_for_batch,
)
from Backend.vPlan.report_generation.weak_language_check import unwrap_requirements

load_dotenv()

VPLAN_BATCH_RETRIES = max(
    0,
    int(os.getenv("VPLAN_BATCH_RETRIES", "2")),
)
VPLAN_CATEGORY_BATCH_SIZE = max(
    1,
    int(os.getenv("VPLAN_CATEGORY_BATCH_SIZE", "40")),
)


SYSTEM_PROMPT = """You are a vPlan generator.

Create a vPlan table from the provided JSON requirements.

Rules:
- Use only the information in the input JSON.
- Requirements are grouped across the whole specification by planning_category.
- planning_subcategory is the consistent finer grouping within that parent category.
- You may use another requirement in this category batch only when it explicitly
  defines a value, condition, signal, outcome, or rule needed by the primary requirement.
- Record every such source in supporting_requirement_ids. Do not cite a merely similar
  requirement, and never cite an ID that is absent from the input batch.
- Do not invent missing technical details.
- Do not include requirement_text. This will be added later from the input requirements file.
- Every requirement must have at least one traceability row. A traceability row marked
  uncovered is not a proposed test and must not contain test content.
- A requirement may have multiple tests if it contains multiple independent behaviours, modes, bit fields, causes, outcomes, reset cases, or software-visible conditions.
- If a requirement contains multiple status bits, command bits, encoded values, or transfer directions, split by each bit, value, or direction.
- Each test must verify one main behaviour only.
- Include negative tests only where the requirement defines a disabled state, forbidden condition, invalid access, error condition, or non-happy-path behaviour.
- Do not invent negative tests if the input JSON does not imply a valid negative scenario.
- Do not split a test just because multiple signals are involved in the same behaviour.
- Multiple rows may share the same requirement_id.
- Each row must have a unique test_id.
- Keep test_steps to 1-3 concise steps.
- Keep expected_results to 1-2 concise results.
- The test_description must directly reflect the specific requirement text. Do not generalise to broader protocol behaviour unless the requirement itself states that behaviour.
- If a requirement is broad, marketing-like, architectural, or lacks measurable behaviour, do not invent a concrete functional test. Create one traceability row and mark it uncovered.
- If a requirement cannot be usefully verified because it lacks observable behaviour, measurable values, signal names, timing rules, or configuration context, mark coverage as uncovered.
- For every uncovered row, set test_name = "", test_description = "", test_steps = [],
  and expected_results = []. Explain why it is uncovered only in test_constraints.
- Never provide possible, illustrative, suggested, placeholder, or future test steps for an
  uncovered row.
- Use partially_covered only when the requirement contains enough explicit information to
  create at least one real, requirement-grounded test action and at least one observable
  expected result. Populate only those supported actions and outcomes.
- If you cannot write a specific executable step and observable expected result using only
  the requirement text, use uncovered, not partially_covered.
- Do not fill gaps in a partially covered requirement with protocol knowledge, assumptions,
  common implementation behaviour, inferred signal values, invented timing, or guessed
  pass/fail criteria.
- Treat wording such as "can", "may", "permitted", and "up to" as capability or permission language, not always mandatory behaviour.
- If a requirement states a maximum, such as "up to 1024 bits", test the boundary only if the requirement clearly implies support for that boundary. Otherwise mark as partially_covered and state that supported configurations are implementation-defined.
- If test_constraints mention missing configuration values, missing thresholds, unspecified signals, or implementation-defined behaviour, coverage should usually be partially_covered or uncovered, not covered.

Scenario types:
- scenario_type and coverage are separate fields with separate meanings.
- scenario_type must contain exactly one of: nominal, illegal, corner.
- Never put covered, partially_covered, or uncovered in scenario_type.
- For an uncovered traceability row with no illegal or boundary behaviour, use scenario_type = nominal and coverage = uncovered.
- Nominal/legal scenario: valid protocol behaviour, valid encodings, expected transitions.
- Illegal/error scenario: forbidden encodings, invalid accesses, protocol violations, disabled-mode behaviour, expected error handling.
- Corner/boundary scenario: legal but stressful edge cases, such as min/max values, transitions at limits, unusual timing, reset-adjacent behaviour.
- Do not mark an opposite valid encoded value as illegal or corner unless it represents an error, disabled state, invalid access, or forbidden behaviour.

Required columns:
test_id, requirement_id, supporting_requirement_ids, scenario_type, test_description,
test_constraints, test_steps, expected_results, coverage.
The test_name is added deterministically after generation; leave it blank if requested by the schema.

Edge-case usage:
- You may be given edge-case candidates linked to requirement_id values.
- Use edge cases to decide whether a requirement is fully testable, partially testable, or uncovered.
- If an edge case shows that behaviour is optional, implementation-dependent, ambiguous, underspecified, or not directly observable, reflect that in test_constraints and lower coverage unless the edge case is irrelevant to the behaviour being tested.
- If the requirement cannot be meaningfully tested from the provided information, still create one traceability row, but mark coverage as uncovered.
- For uncovered rows, state required clarification in test_constraints only. Keep
  test_name, test_description, test_steps, and expected_results empty.
- Do not invent tests to resolve an edge case. Note the limitation instead.
- If a requirement is only partially testable because of an edge case, mark coverage as partially_covered.
- If a requirement describes permitted behaviour rather than mandatory behaviour, do not mark the row as covered unless the test verifies a mandatory constraint. Use partially_covered when the behaviour is allowed but not required.
- If an edge case is linked to a requirement, coverage should usually be partially_covered or uncovered unless the edge case does not affect testability.

Coverage:
- covered = every planned behaviour in this row is explicitly supported, executable, and
  has observable pass/fail evidence in the provided requirement information
- partially_covered = at least one real test is supported, but some required behaviour,
  condition, value, timing, configuration, or expected result remains unspecified
- uncovered = not usefully testable from the provided information
- When uncertain between covered and partially_covered, choose partially_covered.
- When uncertain between partially_covered and uncovered, choose uncovered unless a real
  executable step and observable expected result are explicitly supported.
"""


def invoke_agent(
    requirements_batch: list[dict],
    run_id: uuid.UUID,
    edge_cases: dict | None = None,
    batch_number: int | None = None,
    attempt_number: int = 1,
) -> tuple[dict, dict]:
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not found. Check your .env file.")

    agent = create_agent(
        model="openai:gpt-5.4",
        response_format=Table,
        system_prompt=SYSTEM_PROMPT,
    )

    vplan_input = {
        "requirements": requirements_batch,
        "edge_cases": edge_cases or {"edge_cases": []},
    }

    with get_openai_callback() as callback:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Create a vPlan table from this JSON input. "
                            "Use the edge-case information when deciding whether each requirement is "
                            "covered, partially_covered, or uncovered:\n"
                            f"{json.dumps(vplan_input, separators=(',', ':'))}"
                        ),
                    }
                ]
            },
            config={
                "run_id": run_id,
                "run_name": (
                    f"vplan_generation_batch_{batch_number}"
                    if batch_number is not None
                    else "vplan_generation"
                ),
                "metadata": {
                    "batch_number": batch_number,
                    "batch_size": len(requirements_batch),
                    "attempt_number": attempt_number,
                    "ls_provider": "openai",
                    "ls_model_name": "gpt-5.4",
                },
                "tags": ["vplan-generator", "batched-vplan"],
            },
        )

        usage = normalise_usage(
            agent_name=(
                f"vplan_generator_batch_{batch_number}"
                if batch_number is not None
                else "vplan_generator"
            ),
            input_tokens=callback.prompt_tokens,
            output_tokens=callback.completion_tokens,
            total_tokens=callback.total_tokens,
            total_cost=callback.total_cost,
            model_name="gpt-5.4",
        )

    return result, usage


def invoke_batch_with_retries(
    *,
    requirements_batch: list[dict],
    edge_cases: dict,
    batch_number: int,
) -> tuple[dict, dict, str]:
    """Retry transient or malformed structured output for one batch."""

    last_error: Exception | None = None

    for attempt_number in range(1, VPLAN_BATCH_RETRIES + 2):
        batch_run_id = uuid.uuid4()

        try:
            result, usage = invoke_agent(
                requirements_batch=requirements_batch,
                run_id=batch_run_id,
                edge_cases=edge_cases,
                batch_number=batch_number,
                attempt_number=attempt_number,
            )
            return result, usage, str(batch_run_id)

        except Exception as error:
            last_error = error

            if attempt_number <= VPLAN_BATCH_RETRIES:
                print(
                    f"vPlan batch {batch_number} attempt {attempt_number} failed: "
                    f"{error}. Retrying."
                )

    raise RuntimeError(
        f"vPlan batch {batch_number} failed after "
        f"{VPLAN_BATCH_RETRIES + 1} attempts: {last_error}"
    ) from last_error


def v_plan_agent_call(
    reqs: str,
    edge_cases: dict | None = None,
    batch_size: int | None = None,
) -> dict:
    with open(reqs, "r", encoding="utf-8") as file:
        requirements_data = json.load(file)

    requirements_file = unwrap_requirements(requirements_data)

    print(f"Using requirements file: {reqs}")
    print(f"Total requirements: {len(requirements_file)}")
    max_category_batch_size = batch_size or VPLAN_CATEGORY_BATCH_SIZE
    print("Batching strategy: whole-spec requirement categories")
    print(f"Maximum requirements per category batch: {max_category_batch_size}")

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    main_run_id = uuid.uuid4()

    batches = build_category_batches(
        requirements=requirements_file,
        max_batch_size=max_category_batch_size,
    )

    all_vplan_rows = []
    batch_usages = []
    batch_trace_ids = []

    batch_categories = []

    for batch_index, batch_info in enumerate(batches, start=1):
        batch = batch_info["requirements"]
        category = batch_info["category"]
        category_part = batch_info["category_part"]
        category_parts = batch_info["category_parts"]
        category_suffix = (
            f" part {category_part}/{category_parts}" if category_parts > 1 else ""
        )
        print(
            f"[vPlan batch {batch_index}/{len(batches)}] Starting category "
            f"'{category}'{category_suffix} with {len(batch)} requirements."
        )

        batch_edge_cases = filter_edge_cases_for_batch(
            edge_cases=edge_cases,
            requirements_batch=batch,
        )

        result, usage, batch_trace_id = invoke_batch_with_retries(
            requirements_batch=batch,
            edge_cases=batch_edge_cases,
            batch_number=batch_index,
        )

        batch_vplan = result["structured_response"]

        allowed_requirement_ids = {
            str(requirement.get("id"))
            for requirement in batch
            if requirement.get("id") is not None
        }
        for row in batch_vplan.feature_list:
            # Structured output may still invent or repeat supporting IDs. Only
            # sources actually visible in this batch are retained.
            row.requirement_category = category
            primary_requirement = next(
                (
                    requirement
                    for requirement in batch
                    if str(requirement.get("id")) == row.requirement_id
                ),
                {},
            )
            row.requirement_subcategory = str(
                primary_requirement.get("planning_subcategory", "Uncategorised")
            )
            row.supporting_requirement_ids = sorted(
                {
                    str(requirement_id)
                    for requirement_id in row.supporting_requirement_ids
                    if str(requirement_id) in allowed_requirement_ids
                    and str(requirement_id) != row.requirement_id
                }
            )

        all_vplan_rows.extend(batch_vplan.feature_list)
        batch_usages.append(usage)
        batch_trace_ids.append(batch_trace_id)
        batch_categories.append(category)
        print(
            f"[vPlan batch {batch_index}/{len(batches)}] Completed category "
            f"'{category}' with {len(batch_vplan.feature_list)} vPlan rows."
        )

    feature_list = [row.model_dump() for row in all_vplan_rows]

    feature_list = ensure_unique_test_ids(feature_list)

    metadata = {
        "requirements_file": Path(reqs).name,
        "date_created": now.strftime("%B %d %Y"),
        "time_created": now.strftime("%I:%M%p").lower(),
        "number_of_requirements": len(requirements_file),
        "number_of_tests": len(feature_list),
        "batching_strategy": "requirement_category_with_size_cap",
        "max_category_batch_size": max_category_batch_size,
        "number_of_batches": len(batches),
        "batch_categories": batch_categories,
        "number_of_edge_case_candidates": len((edge_cases or {}).get("edge_cases", [])),
        "langsmith_trace_id": str(main_run_id),
        "batch_trace_ids": batch_trace_ids,
    }

    output_json = {
        "metadata": metadata,
        "feature_list": feature_list,
    }

    output_json = add_requirement_text(
        vplan_data=output_json,
        requirements=requirements_file,
    )

    generated_vplan_file = VPLAN_DIR / f"generated_vplan_{timestamp}.json"

    with open(generated_vplan_file, "w", encoding="utf-8") as f:
        json.dump(output_json, f, indent=2)

    print(f"Generated vPlan saved to {generated_vplan_file}")

    usage = combine_usage(batch_usages)

    try:
        check_traceability(
            requirements_file=reqs,
            generated_vplan_file=generated_vplan_file,
        )
    except Exception as error:
        print(f"Traceability check failed, but vPlan was generated: {error}")

    return {
        "vplan_output_file": str(generated_vplan_file),
        "vplan": output_json,
        "vplan_trace_id": str(main_run_id),
        "vplan_batch_trace_ids": batch_trace_ids,
        "vplan_usage": usage,
    }
