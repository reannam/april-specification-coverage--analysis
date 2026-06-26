from langchain.agents import create_agent
from Backend.data_class import Table
import json
from dotenv import load_dotenv
import os
from datetime import datetime
from pathlib import Path
from Backend.vplan_traceability_check import check_traceability, add_requirement_text
import uuid
from langchain_community.callbacks.manager import get_openai_callback
from Backend.usage_logger import normalise_usage

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]

OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LANGSMITH_LOGS_DIR = OUTPUT_DIR / "langsmith_logs"
LANGSMITH_LOGS_DIR.mkdir(parents=True, exist_ok=True)

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found. Check your .env file.")


SYSTEM_PROMPT = """You are a vPlan generator.

Create a vPlan table from the provided JSON requirements.

Rules:
- Use only the information in the input JSON.
- Do not invent missing technical details.
- Do not include requirement_text or requirement_description. These will be added later from the input requirements file.
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
test_id, requirement_id, test_type, test_description, test_constraints, test_steps, expected_results, priority, coverage.

Coverage:
- covered = directly testable from the provided information
- partially_covered = only partly testable from the provided information
- blocked = not usefully testable from the provided information

Priority:
- 1 = high priority functional/protocol/register/reset/interrupt behaviour
- 2 = medium priority integration or externally dependent behaviour
- 3 = lower priority software guidance or unclear hardware enforcement
"""


agent = create_agent(
    model="openai:gpt-5.4",
    response_format=Table,
    system_prompt=SYSTEM_PROMPT,
)

def invoke_agent(requirements, run_id: uuid.UUID) -> tuple[dict, dict]:
    """Invoke the agent using the requirements JSON file and capture token usage."""

    with open(requirements, "r", encoding="utf-8") as file:
        specification = json.load(file)

    with get_openai_callback() as callback:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Create a vPlan table from this JSON specification:\n"
                            f"{json.dumps(specification, separators=(',', ':'))}"
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


def v_plan_agent_call(reqs: str) -> dict:
    with open(reqs, "r", encoding="utf-8") as file:
        requirements_file = json.load(file)

    print(f"Using requirements file: {reqs}")

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    run_id = uuid.uuid4()

    result, usage = invoke_agent(reqs, run_id=run_id)

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