from langchain.agents import create_agent
from data_class import Table
import json
from dotenv import load_dotenv
import os
from datetime import datetime
from pathlib import Path
import argparse
from vplan_traceability_check import check_traceability, add_requirement_text
import uuid
from langsmith_trace_export import save_langsmith_trace_log

load_dotenv()

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

REQUIREMENTS_FILE = "../example-requirements.json"

agent = create_agent(
    model="openai:gpt-5.4",
    response_format=Table,
    system_prompt=SYSTEM_PROMPT,
)

def invoke_agent(requirements, run_id: uuid.UUID) -> dict:
    """Invoke the agent using the requirements JSON file."""

    with open(requirements, "r") as file:
        specification = json.load(file)

    return agent.invoke(
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
            },
            "tags": ["vplan-generator"],
        },
    )


OUTPUT_DIR = Path("../outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="File path of requirements")

    parser.add_argument(
        "--file",
        action="store",
        dest="requirements_file",
        default=REQUIREMENTS_FILE,
    )

    args = parser.parse_args()

    print(f"Using requirements file: {args.requirements_file}")

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    run_id = uuid.uuid4()

    result = invoke_agent(args.requirements_file, run_id=run_id)

    vplan = result["structured_response"]

    now = datetime.now()

    with open(args.requirements_file, "r", encoding="utf-8") as file:
        input_requirements = json.load(file)

    metadata = {
        "requirements_file": Path(args.requirements_file).name,
        "date_created": now.strftime("%B %d %Y"),
        "time_created": now.strftime("%I:%M%p").lower(),
        "number_of_requirements": len(input_requirements),
        "number_of_tests": len(vplan.feature_list),
        "langsmith_trace_id": str(run_id),
    }

    output_json = {
        "metadata": metadata,
        **vplan.model_dump()
    }

    output_json = add_requirement_text(
        vplan_data=output_json,
        requirements=input_requirements,
    )

    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    generated_vplan_file = OUTPUT_DIR / f"generated_vplan_{timestamp}.json"

    with open(generated_vplan_file, "w", encoding="utf-8") as f:
        json.dump(output_json, f, indent=2)

    LANGSMITH_LOGS_DIR = OUTPUT_DIR / "langsmith_logs"

    save_langsmith_trace_log(
        run_id=run_id,
        output_file=generated_vplan_file,
        logs_dir=LANGSMITH_LOGS_DIR,
    )

    print(f"Generated vPlan saved to {generated_vplan_file}")

    check_traceability(
        requirements_file=args.requirements_file,
        generated_vplan_file=generated_vplan_file,
    )