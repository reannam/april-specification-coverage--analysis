from pathlib import Path
from datetime import datetime
import json
import os
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent

from Backend.data_class import CoverageReport

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found. Check your .env file.")


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "outputs"
COVERAGE_OUTPUT_DIR = OUTPUT_DIR / "coverage_reports"
COVERAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


COVERAGE_ANALYSIS_PROMPT = """You are a verification coverage analysis agent.

You are given:
1. A JSON requirements file.
2. A generated verification plan file.

Your task is to check whether the vPlan covers every requirement well.

Rules:
- Use only the provided requirements and vPlan.
- Do not invent missing behaviours, signals, registers, modes, or expected outcomes.
- Do not generate a new vPlan.
- Do not create new tests, except when briefly describing a suggested action.
- Return exactly one coverage finding for every source requirement.
- Assess coverage requirement by requirement.
- A requirement is covered only if the vPlan verifies all explicit behaviours in that requirement.
- A requirement is partially covered if at least one explicit behaviour is tested, but another explicit behaviour is missing, vague, or incomplete.
- A requirement is not covered if no vPlan test meaningfully verifies the requirement.
- A requirement is blocked if coverage cannot be judged because the requirement itself or the mapped vPlan content is too vague or incomplete.
- Match tests to requirements primarily using requirement_id.
- If a test references the correct requirement_id but does not actually verify the required behaviour, do not mark it as covered.
- If a requirement has multiple independent behaviours, fields, modes, reset cases, status bits, command bits, causes, outcomes, or software-visible conditions, all must be covered for the requirement to be marked covered.
- Be specific about what is covered and what is missing.
- Keep reasoning concise and evidence-based.

Coverage statuses:
- covered
- partially_covered
- not_covered
- blocked

Important:
- The final report must include every source requirement exactly once.
- Do not skip requirements.
- Do not assume matching IDs alone mean coverage.
"""


coverage_agent = create_agent(
    model=os.getenv("COVERAGE_MODEL", "openai:gpt-5.4"),
    system_prompt=COVERAGE_ANALYSIS_PROMPT,
    response_format=CoverageReport,
)


def load_json_file(file_path: str | Path) -> Any:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() != ".json":
        raise ValueError(f"Expected a JSON file, got: {path.name}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_requirements(requirements_json: Any) -> list[dict[str, Any]]:
    """
    Supports either:
    - a raw list of requirements
    - {"requirements": [...]}
    - {"feature_list": [...]} if needed later
    """

    if isinstance(requirements_json, list):
        return requirements_json

    if isinstance(requirements_json, dict):
        for key in ["requirements", "feature_list", "items"]:
            if key in requirements_json and isinstance(requirements_json[key], list):
                return requirements_json[key]

    raise ValueError(
        "Could not find requirements list. Expected a list or a dict containing "
        "'requirements', 'feature_list', or 'items'."
    )


def extract_vplan_rows(vplan_json: Any) -> list[dict[str, Any]]:
    """
    Supports common vPlan shapes:
    - {"feature_list": [...]}
    - {"tests": [...]}
    - {"vplan": [...]}
    - raw list
    """

    if isinstance(vplan_json, list):
        return vplan_json

    if isinstance(vplan_json, dict):
        for key in ["feature_list", "tests", "vplan", "rows"]:
            if key in vplan_json and isinstance(vplan_json[key], list):
                return vplan_json[key]

        if "table" in vplan_json and isinstance(vplan_json["table"], dict):
            table = vplan_json["table"]
            for key in ["feature_list", "tests", "rows"]:
                if key in table and isinstance(table[key], list):
                    return table[key]

    raise ValueError(
        "Could not find vPlan rows. Expected a list or a dict containing "
        "'feature_list', 'tests', 'vplan', or 'rows'."
    )


def get_requirement_id(requirement: dict[str, Any]) -> str | None:
    return requirement.get("id") or requirement.get("requirement_id")


def get_requirement_text(requirement: dict[str, Any]) -> str:
    return (
        requirement.get("description")
        or requirement.get("requirement_text")
        or requirement.get("text")
        or ""
    )


def get_test_requirement_id(test: dict[str, Any]) -> str | None:
    return test.get("requirement_id") or test.get("id")


def get_test_id(test: dict[str, Any]) -> str | None:
    return test.get("test_id")


def validate_inputs(
    requirements: list[dict[str, Any]],
    vplan_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    validation_errors: list[str] = []

    requirement_ids = []
    for requirement in requirements:
        requirement_id = get_requirement_id(requirement)

        if not requirement_id:
            validation_errors.append(
                f"Requirement missing ID: {requirement}"
            )
            continue

        requirement_ids.append(requirement_id)

    duplicate_requirement_ids = sorted(
        {
            requirement_id
            for requirement_id in requirement_ids
            if requirement_ids.count(requirement_id) > 1
        }
    )

    if duplicate_requirement_ids:
        validation_errors.append(
            f"Duplicate requirement IDs found: {duplicate_requirement_ids}"
        )

    vplan_requirement_ids = {
        get_test_requirement_id(test)
        for test in vplan_rows
        if get_test_requirement_id(test)
    }

    missing_requirement_ids = sorted(
        set(requirement_ids) - vplan_requirement_ids
    )

    tests_missing_ids = [
        index
        for index, test in enumerate(vplan_rows)
        if not get_test_id(test)
    ]

    tests_missing_requirement_ids = [
        index
        for index, test in enumerate(vplan_rows)
        if not get_test_requirement_id(test)
    ]

    if tests_missing_ids:
        validation_errors.append(
            f"vPlan rows missing test_id at indexes: {tests_missing_ids}"
        )

    if tests_missing_requirement_ids:
        validation_errors.append(
            "vPlan rows missing requirement_id at indexes: "
            f"{tests_missing_requirement_ids}"
        )

    return {
        "validation_errors": validation_errors,
        "missing_requirement_ids": missing_requirement_ids,
    }


def build_agent_payload(
    requirements: list[dict[str, Any]],
    vplan_rows: list[dict[str, Any]],
    validation_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "requirements": requirements,
        "vplan_rows": vplan_rows,
        "deterministic_precheck": {
            "requirements_count": len(requirements),
            "vplan_rows_count": len(vplan_rows),
            "missing_requirement_ids_in_vplan": validation_result[
                "missing_requirement_ids"
            ],
            "validation_errors": validation_result[
                "validation_errors"
            ],
        },
        "instruction": (
            "Assess whether the vPlan fully covers each requirement. "
            "Return one finding per requirement."
        ),
    }


def recompute_summary(report: dict[str, Any]) -> dict[str, Any]:
    findings = report.get("findings", [])

    total_requirements = len(findings)
    covered_count = sum(
        1 for item in findings if item.get("coverage_status") == "covered"
    )
    partially_covered_count = sum(
        1 for item in findings if item.get("coverage_status") == "partially_covered"
    )
    not_covered_count = sum(
        1 for item in findings if item.get("coverage_status") == "not_covered"
    )
    blocked_count = sum(
        1 for item in findings if item.get("coverage_status") == "blocked"
    )

    coverage_percentage = (
        round((covered_count / total_requirements) * 100, 2)
        if total_requirements > 0
        else 0.0
    )

    report["summary"] = {
        "total_requirements": total_requirements,
        "covered_count": covered_count,
        "partially_covered_count": partially_covered_count,
        "not_covered_count": not_covered_count,
        "blocked_count": blocked_count,
        "coverage_percentage": coverage_percentage,
    }

    return report


def enforce_missing_requirement_findings(
    report: dict[str, Any],
    requirements: list[dict[str, Any]],
    missing_requirement_ids: list[str],
) -> dict[str, Any]:
    """
    Safety check:
    If a requirement ID never appears in the vPlan, it cannot be covered.
    This prevents the LLM from accidentally marking it as covered.
    """

    if not missing_requirement_ids:
        return report

    missing_set = set(missing_requirement_ids)
    findings = report.get("findings", [])

    finding_by_requirement_id = {
        finding.get("requirement_id"): finding
        for finding in findings
    }

    for requirement in requirements:
        requirement_id = get_requirement_id(requirement)

        if requirement_id not in missing_set:
            continue

        requirement_text = get_requirement_text(requirement)

        if requirement_id in finding_by_requirement_id:
            finding = finding_by_requirement_id[requirement_id]
            finding["coverage_status"] = "not_covered"
            finding["matched_test_ids"] = []
            finding["covered_behaviours"] = []
            finding["missing_behaviours"] = [
                requirement_text or "The full requirement is missing from the vPlan."
            ]
            finding["reasoning"] = (
                "No vPlan row references this requirement ID, so the requirement "
                "cannot be considered covered."
            )
            finding["suggested_action"] = (
                "Add one or more vPlan tests that explicitly verify this requirement."
            )
        else:
            findings.append(
                {
                    "requirement_id": requirement_id,
                    "requirement_text": requirement_text,
                    "coverage_status": "not_covered",
                    "matched_test_ids": [],
                    "covered_behaviours": [],
                    "missing_behaviours": [
                        requirement_text or "The full requirement is missing from the vPlan."
                    ],
                    "reasoning": (
                        "No vPlan row references this requirement ID, so the requirement "
                        "cannot be considered covered."
                    ),
                    "suggested_action": (
                        "Add one or more vPlan tests that explicitly verify this requirement."
                    ),
                }
            )

    report["findings"] = findings
    return report


def save_coverage_report(
    coverage_report: dict[str, Any],
    requirements_file: str | Path,
    vplan_file: str | Path,
) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    requirements_stem = Path(requirements_file).stem
    vplan_stem = Path(vplan_file).stem

    output_file = (
        COVERAGE_OUTPUT_DIR
        / f"coverage_report_{requirements_stem}_{vplan_stem}_{timestamp}.json"
    )

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(coverage_report, file, indent=2)

    return output_file


def coverage_analysis_agent_call(
    requirements_file: str,
    vplan_file: str,
) -> dict[str, Any]:
    requirements_json = load_json_file(requirements_file)
    vplan_json = load_json_file(vplan_file)

    requirements = extract_requirements(requirements_json)
    vplan_rows = extract_vplan_rows(vplan_json)

    validation_result = validate_inputs(
        requirements=requirements,
        vplan_rows=vplan_rows,
    )

    agent_payload = build_agent_payload(
        requirements=requirements,
        vplan_rows=vplan_rows,
        validation_result=validation_result,
    )

    result = coverage_agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(agent_payload, indent=2),
                }
            ]
        }
    )

    structured_response = result["structured_response"]
    coverage_report = structured_response.model_dump()

    coverage_report = enforce_missing_requirement_findings(
        report=coverage_report,
        requirements=requirements,
        missing_requirement_ids=validation_result["missing_requirement_ids"],
    )

    coverage_report = recompute_summary(coverage_report)

    output_file = save_coverage_report(
        coverage_report=coverage_report,
        requirements_file=requirements_file,
        vplan_file=vplan_file,
    )

    return {
        "coverage_report": coverage_report,
        "coverage_output_file": str(output_file),
        "coverage_validation_errors": validation_result["validation_errors"],
        "coverage_missing_requirement_ids": validation_result["missing_requirement_ids"],
    }