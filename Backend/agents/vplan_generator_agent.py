from pathlib import Path
from datetime import datetime
import json
import os
import uuid

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_community.callbacks.manager import get_openai_callback

from Backend.pre_processing.data_class import Table
from Backend.report_generation.vplan_traceability_check import (
    check_traceability,
    add_requirement_text,
)
from Backend.post_processing.usage_logger import normalise_usage
from Backend.report_generation.weak_language_check import unwrap_requirements

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]

OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LANGSMITH_LOGS_DIR = OUTPUT_DIR / "langsmith_logs"
LANGSMITH_LOGS_DIR.mkdir(parents=True, exist_ok=True)


SYSTEM_PROMPT = """You are a vPlan generator.

Create a vPlan table from the provided JSON requirements.

Rules:
- Use only the information in the input JSON.
- Do not invent missing technical details.
- Do not include requirement_text. This will be added later from the input requirements file.
- Every requirement must have at least one test.
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
- If a requirement is broad, marketing-like, architectural, or lacks measurable behaviour, do not invent a concrete functional test. Create one traceability row and mark coverage as blocked or partially_covered.
- If a requirement cannot be usefully verified because it lacks observable behaviour, measurable values, signal names, timing rules, or configuration context, mark coverage as blocked.
- For blocked rows, test_steps should identify the missing information needed for verification rather than pretending to execute a real test.
- Treat wording such as "can", "may", "permitted", and "up to" as capability or permission language, not always mandatory behaviour.
- If a requirement states a maximum, such as "up to 1024 bits", test the boundary only if the requirement clearly implies support for that boundary. Otherwise mark as partially_covered and state that supported configurations are implementation-defined.
- If test_constraints mention missing configuration values, missing thresholds, unspecified signals, or implementation-defined behaviour, coverage should usually be partially_covered or blocked, not covered.

Test types:
- positive = normal valid behaviour, including valid modes, valid encoded values, and expected state transitions.
- negative = disabled, invalid, forbidden, error, access-violation, or non-happy-path behaviour.
- Do not mark an opposite valid encoded value as negative unless it represents an error, disabled state, invalid access, or forbidden behaviour.

Required columns:
test_id, requirement_id, test_type, test_description, test_constraints, test_steps, expected_results, coverage.

Edge-case usage:
- You may be given edge-case candidates linked to requirement_id values.
- Use edge cases to decide whether a requirement is fully testable, partially testable, or blocked.
- If an edge case shows that behaviour is optional, implementation-dependent, ambiguous, underspecified, or not directly observable, reflect that in test_constraints and coverage.
- If the requirement cannot be meaningfully tested from the provided information, still create one traceability row, but mark coverage as blocked.
- For blocked rows, test_steps should state what information, implementation detail, configuration value, or clarification is required before verification can proceed.
- Do not invent tests to resolve an edge case. Note the limitation instead.
- If a requirement is only partially testable because of an edge case, mark coverage as partially_covered.
- If a requirement describes permitted behaviour rather than mandatory behaviour, do not mark the row as covered unless the test verifies a mandatory constraint. Use partially_covered when the behaviour is allowed but not required.
- If an edge case is linked to a requirement, coverage should usually be partially_covered or blocked unless the edge case does not affect testability.

Coverage:
- covered = directly testable from the provided information
- partially_covered = only partly testable from the provided information
- blocked = not usefully testable from the provided information
"""


agent = create_agent(
    model="openai:gpt-5.4",
    response_format=Table,
    system_prompt=SYSTEM_PROMPT,
)


def chunk_requirements(
    requirements: list[dict],
    batch_size: int = 30,
) -> list[list[dict]]:
    """Split requirements into smaller batches for safer vPlan generation."""

    return [
        requirements[index : index + batch_size]
        for index in range(0, len(requirements), batch_size)
    ]


def filter_edge_cases_for_batch(
    edge_cases: dict | None,
    requirements_batch: list[dict],
) -> dict:
    """Keep only edge cases relevant to the current requirements batch."""

    if not edge_cases:
        return {"edge_cases": []}

    batch_requirement_ids = {
        requirement.get("id")
        for requirement in requirements_batch
        if isinstance(requirement, dict) and requirement.get("id")
    }

    return {
        "edge_cases": [
            edge_case
            for edge_case in edge_cases.get("edge_cases", [])
            if edge_case.get("requirement_id") in batch_requirement_ids
        ]
    }


def ensure_unique_test_ids(rows: list[dict]) -> list[dict]:
    """Ensure merged batched outputs do not contain duplicate test IDs."""

    seen: dict[str, int] = {}

    for row in rows:
        test_id = row.get("test_id") or "TEST_UNKNOWN"

        if test_id not in seen:
            seen[test_id] = 1
            row["test_id"] = test_id
            continue

        seen[test_id] += 1
        row["test_id"] = f"{test_id}_DUP{seen[test_id]}"

    return rows


def to_int(value) -> int:
    if value is None:
        return 0

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def to_float(value) -> float:
    if value is None:
        return 0.0

    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "").strip()

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def combine_usage(batch_usages: list[dict]) -> dict:
    """Combine usage from all vPlan batches into one agent-level usage record."""

    prompt_tokens = sum(to_int(usage.get("prompt_tokens")) for usage in batch_usages)

    completion_tokens = sum(
        to_int(usage.get("completion_tokens")) for usage in batch_usages
    )

    total_tokens = sum(to_int(usage.get("total_tokens")) for usage in batch_usages)

    total_cost = sum(to_float(usage.get("total_cost")) for usage in batch_usages)

    combined = normalise_usage(
        agent_name="vplan_generator",
        input_tokens=prompt_tokens,
        output_tokens=completion_tokens,
        total_tokens=total_tokens,
        total_cost=total_cost,
        model_name="gpt-5.4",
    )

    combined["number_of_batches"] = len(batch_usages)
    combined["batches"] = batch_usages

    return combined


def invoke_agent(
    requirements_batch: list[dict],
    run_id: uuid.UUID,
    edge_cases: dict | None = None,
    batch_number: int | None = None,
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
                            "covered, partially_covered, or blocked:\n"
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


def v_plan_agent_call(
    reqs: str,
    edge_cases: dict | None = None,
    batch_size: int = 30,
) -> dict:
    with open(reqs, "r", encoding="utf-8") as file:
        requirements_data = json.load(file)

    requirements_file = unwrap_requirements(requirements_data)

    print(f"Using requirements file: {reqs}")
    print(f"Total requirements: {len(requirements_file)}")
    print(f"Batch size: {batch_size}")

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    main_run_id = uuid.uuid4()

    batches = chunk_requirements(
        requirements=requirements_file,
        batch_size=batch_size,
    )

    all_vplan_rows = []
    batch_usages = []
    batch_trace_ids = []

    for batch_index, batch in enumerate(batches, start=1):
        print(
            f"Running vPlan batch {batch_index}/{len(batches)} "
            f"with {len(batch)} requirements"
        )

        batch_edge_cases = filter_edge_cases_for_batch(
            edge_cases=edge_cases,
            requirements_batch=batch,
        )

        batch_run_id = uuid.uuid4()

        result, usage = invoke_agent(
            requirements_batch=batch,
            run_id=batch_run_id,
            edge_cases=batch_edge_cases,
            batch_number=batch_index,
        )

        batch_vplan = result["structured_response"]

        all_vplan_rows.extend(batch_vplan.feature_list)
        batch_usages.append(usage)
        batch_trace_ids.append(str(batch_run_id))

    feature_list = [row.model_dump() for row in all_vplan_rows]

    feature_list = ensure_unique_test_ids(feature_list)

    metadata = {
        "requirements_file": Path(reqs).name,
        "date_created": now.strftime("%B %d %Y"),
        "time_created": now.strftime("%I:%M%p").lower(),
        "number_of_requirements": len(requirements_file),
        "number_of_tests": len(feature_list),
        "batch_size": batch_size,
        "number_of_batches": len(batches),
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

    generated_vplan_file = OUTPUT_DIR / f"generated_vplan_{timestamp}.json"

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
