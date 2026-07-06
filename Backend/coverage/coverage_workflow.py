from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from Backend.data_class import CoverageGraphState
from Backend.agents.coverage_analysis_agent import coverage_analysis_agent_call

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"

WORKFLOW_IMAGE_DIR = OUTPUT_DIR / "node_architecture_graph"
WORKFLOW_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

WORKFLOW_IMAGE_PATH = WORKFLOW_IMAGE_DIR / "coverage_architecture.png"


def coverage_analysis_node(state: CoverageGraphState) -> dict:
    return coverage_analysis_agent_call(
        requirements_file=state["requirements_file"],
        vplan_file=state["vplan_file"],
    )


def save_workflow_image(chain) -> None:
    try:
        image_bytes = chain.get_graph().draw_mermaid_png()
        WORKFLOW_IMAGE_PATH.write_bytes(image_bytes)
        print(f"Coverage workflow image saved to {WORKFLOW_IMAGE_PATH}")

    except Exception as error:
        print(f"Could not save coverage workflow image: {error}")


def build_coverage_workflow():
    workflow = StateGraph(CoverageGraphState)

    workflow.add_node("coverage_analysis_output", coverage_analysis_node)

    workflow.add_edge(START, "coverage_analysis_output")
    workflow.add_edge("coverage_analysis_output", END)

    chain = workflow.compile()

    print("Compiled coverage analysis agent")

    save_workflow_image(chain)

    return chain