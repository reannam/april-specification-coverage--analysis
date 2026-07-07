from pathlib import Path
import argparse

from Backend.config import BASE_DIR
from Backend.pre_processing.agent_scheduler import build_workflow

DEFAULT_REQUIREMENTS_FILE = BASE_DIR / "example-requirements.json"


def run_agents(requirements_file: str | Path = DEFAULT_REQUIREMENTS_FILE):
    workflow = build_workflow()

    result = workflow.invoke({"requirements_file": str(requirements_file)})

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the specification analysis workflow."
    )
    parser.add_argument(
        "requirements_file",
        nargs="?",
        default=str(DEFAULT_REQUIREMENTS_FILE),
        help="Path to the uploaded-style specification JSON file.",
    )

    args = parser.parse_args()

    result = run_agents(args.requirements_file)

    print("Workflow completed")
    print(f"Preprocessed requirements: {result.get('preprocessed_requirements_file')}")
    print(f"vPlan: {result.get('vplan_output_file')}")
    print(f"Edge cases: {result.get('edge_case_output_file')}")
    print(f"Requirement-test links: {result.get('requirement_test_links_file')}")
    print(f"LangSmith log: {result.get('langsmith_log_file')}")


if __name__ == "__main__":
    main()
