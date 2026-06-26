from pathlib import Path
from Backend.agent_scheduler import build_workflow

BASE_DIR = Path(__file__).resolve().parent.parent
REQUIREMENTS_FILE = BASE_DIR / "example-requirements.json"


def run_agents():
    workflow = build_workflow()

    result = workflow.invoke({
        "requirements_file": str(REQUIREMENTS_FILE)
    })

    return result


if __name__ == "__main__":
    result = run_agents()

    print("Workflow completed")
    print(f"vPlan: {result.get('vplan_output_file')}")
    print(f"Edge cases: {result.get('edge_case_output_file')}")