from pathlib import Path
from datetime import datetime
import json

from dotenv import load_dotenv

from langchain.agents import create_agent

from Backend.weak_language_check import (
    run_weak_language_checker,
    check_requirement_language,
    get_flagged_requirements,
    unwrap_requirements,
)
from Backend.data_class import EdgeCaseCandidateList

import uuid
from langchain_community.callbacks.manager import get_openai_callback
from Backend.usage_logger import normalise_usage

BASE_DIR = Path(__file__).resolve().parents[2]

OUTPUT_DIR = BASE_DIR / "outputs"
EDGE_CASE_DIR = OUTPUT_DIR / "edge_cases"
EDGE_CASE_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv()

EDGE_CASE_EXTRACTOR_PROMPT = """You are an edge-case extractor for hardware/software requirements.

You are given:
    - A list of requirements that have been categorised as weak by a deterministic weak language checker
    - The language issues found for those requirements

Your task is to identify edge-cases implied by weak, ambiguous or conditional wording.

Focus on edge-cases created due to language like:
    - May
    - Should
    - Where applicable
    - Normally
    - Could
    - If supported
    - As appropriate

Rules:
    - Do not perform a general quality check
    - Focus only on edge-case scenarios
    - Focus only on issues that would impact a verification engineer
    - Do not invent any behaviours
    - Some requirements will have multiple edge cases, others will have none. Do not make them up.
    - Assume there will be very few requirements containing an edge-case in relation to the whole specification
    - For missing strong requirement language, use trigger_phrase = "missing_strong_requirement_language".
    - The weak language checker is intentionally recall-heavy and may include false positives. If a flagged requirement does not imply a meaningful edge case, return not_an_edge_case and no_action.
"""


edge_case_extractor_agent = create_agent(
    model="openai:gpt-5.4",
    response_format=EdgeCaseCandidateList,
    system_prompt=EDGE_CASE_EXTRACTOR_PROMPT,
)


def extract_edge_cases(
    flagged_requirements: list[dict],
    language_issues: list[dict],
    requirements_file_name: str,
) -> tuple[EdgeCaseCandidateList, dict, str]:
    """Extract edge-case candidates from weak or ambiguous requirement language."""

    run_id = uuid.uuid4()

    edge_case_input = {
        "flagged_requirements": flagged_requirements,
        "language_issues": language_issues,
    }

    with get_openai_callback() as callback:
        result = edge_case_extractor_agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Extract verification edge cases from these weak or ambiguous "
                            "requirements:\n"
                            f"{json.dumps(edge_case_input, separators=(',', ':'))}"
                        ),
                    }
                ]
            },
            config={
                "run_id": run_id,
                "run_name": "edge_case_extraction",
                "metadata": {
                    "requirements_file": requirements_file_name,
                    "ls_provider": "openai",
                    "ls_model_name": "gpt-5.4",
                },
                "tags": ["edge-case-extractor"],
            },
        )

        usage = normalise_usage(
            agent_name="edge_case_extractor",
            input_tokens=callback.prompt_tokens,
            output_tokens=callback.completion_tokens,
            total_tokens=callback.total_tokens,
            total_cost=callback.total_cost,
            model_name="gpt-5.4",
        )

    return result["structured_response"], usage, str(run_id)

def edge_case_agent_call(requirements: str) -> dict:
    print(f"Using requirements file: {requirements}")

    with open(requirements, "r", encoding="utf-8") as file:
        input_data = json.load(file)

    input_requirements = unwrap_requirements(input_data)

    weak_language_file = run_weak_language_checker(requirements)
    issues = check_requirement_language(input_requirements)

    flagged_requirements = get_flagged_requirements(
        requirements=input_requirements,
        language_issues=issues,
    )

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

    edge_cases, usage, edge_case_trace_id = extract_edge_cases(
        flagged_requirements=flagged_requirements,
        language_issues=issues,
        requirements_file_name=Path(requirements).name,
    )

    metadata = {
        "requirements_file": requirements,
        "weak_language_file": str(weak_language_file),
        "date_created": now.strftime("%B %d %Y"),
        "time_created": now.strftime("%I:%M%p").lower(),
        "total_requirements": len(input_requirements),
        "number_of_weak_language_instances": len(issues),
        "number_of_flagged_requirements": len(flagged_requirements),
        "number_of_edge_case_candidates": len(edge_cases.edge_cases),
        "langsmith_trace_id": edge_case_trace_id,
    }

    output_json = {
        "metadata": metadata,
        **edge_cases.model_dump(),
    }

    generated_edge_case_info = EDGE_CASE_DIR / f"generated_edge_case_info_{timestamp}.json"

    with open(generated_edge_case_info, "w", encoding="utf-8") as f:
        json.dump(output_json, f, indent=2)

    print(f"Generated edge-case info saved to {generated_edge_case_info}")

    return {
        "edge_cases": edge_cases.model_dump(),
        "edge_case_output_file": str(generated_edge_case_info),
        "edge_case_trace_id": edge_case_trace_id,
        "edge_case_usage": usage,
    }