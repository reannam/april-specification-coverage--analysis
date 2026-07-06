from pathlib import Path
from datetime import datetime
import json
import os
import uuid

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_community.callbacks.manager import get_openai_callback

from Backend.config import OUTPUT_DIR, LANGSMITH_LOGS_DIR
from Backend.pre_processing.data_class import Table
from Backend.report_generation.vplan_traceability_check import check_traceability, add_requirement_text
from Backend.post_processing.usage_logger import normalise_usage
from Backend.report_generation.weak_language_check import unwrap_requirements

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found. Check your .env file.")


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

def invoke_agent(
        requirements: str,
        run_id: uuid.UUID,
        edge_cases: dict | None = None,
    ) -> tuple[dict, dict]:
    """Invoke the agent using the requirements JSON file and capture token usage."""

    with open(requirements, "r", encoding="utf-8") as file:
        specification_data = json.load(file)

    specification = unwrap_requirements(specification_data)

    vplan_input = {
        "requirements": specification,
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
                "run_name": "vplan_generation",
                "metadata": {
                    "requirements_file": Path(requirements).name,
                    "ls_provider": "openai",
                    "ls_model_name": "gpt-5.4",
                },
                "tags": ["vplan-generator"],
            },
        )

        usage = normalise_usage(
            agent_name="vplan_generator",
            input_tokens=callback.prompt_tokens,
            output_tokens=callback.completion_tokens,
            total_tokens=callback.total_tokens,
            total_cost=callback.total_cost,
            model_name="gpt-5.4",
        )

    return result, usage

def v_plan_agent_call(reqs: str, edge_cases: dict | None = None) -> dict:
    with open(reqs, "r", encoding="utf-8") as file:
        requirements_data = json.load(file)

    requirements_file = unwrap_requirements(requirements_data)

    print(f"Using requirements file: {reqs}")

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    run_id = uuid.uuid4()

    result, usage = invoke_agent(
        requirements=reqs,
        run_id=run_id,
        edge_cases=edge_cases,
    )

    vplan = result["structured_response"]

    metadata = {
        "requirements_file": Path(reqs).name,
        "date_created": now.strftime("%B %d %Y"),
        "time_created": now.strftime("%I:%M%p").lower(),
        "number_of_requirements": len(requirements_file),
        "number_of_tests": len(vplan.feature_list),
        "langsmith_trace_id": str(run_id),
    }

    output_json = {
        "metadata": metadata,
        **vplan.model_dump(),
    }

    output_json = add_requirement_text(
        vplan_data=output_json,
        requirements=requirements_file,
    )

    generated_vplan_file = OUTPUT_DIR / f"generated_vplan_{timestamp}.json"

    with open(generated_vplan_file, "w", encoding="utf-8") as f:
        json.dump(output_json, f, indent=2)

    print(f"Generated vPlan saved to {generated_vplan_file}")

    check_traceability(
        requirements_file=reqs,
        generated_vplan_file=generated_vplan_file,
    )

    return {
        "vplan_output_file": str(generated_vplan_file),
        "vplan": output_json,
        "vplan_trace_id": str(run_id),
        "vplan_usage": usage,
    }