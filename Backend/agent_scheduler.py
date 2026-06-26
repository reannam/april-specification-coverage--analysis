from pathlib import Path

from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv

from Backend.data_class import GraphState
from Backend.agents.edge_case_agent import edge_case_agent_call
from Backend.agents.vplan_generator_agent import v_plan_agent_call
from Backend.usage_logger import aggregate_usage, save_usage_log
from Backend.analyse_usage_logs import generate_usage_reports

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"

USAGE_LOGS_DIR = OUTPUT_DIR / "langsmith_logs"
USAGE_LOGS_DIR.mkdir(parents=True, exist_ok=True)

WORKFLOW_IMAGE_DIR = OUTPUT_DIR / "node_architecture_graph"
WORKFLOW_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

WORKFLOW_IMAGE_PATH = WORKFLOW_IMAGE_DIR / "architecture.png"


def vplan_node(state: GraphState) -> dict:
    return v_plan_agent_call(state["requirements_file"])


def edge_case_node(state: GraphState) -> dict:
    return edge_case_agent_call(state["requirements_file"])


def usage_summary_node(state: GraphState) -> dict:
    vplan_usage = state.get("vplan_usage", {})
    edge_case_usage = state.get("edge_case_usage", {})

    summary = aggregate_usage(vplan_usage, edge_case_usage)

    vplan_output_file = state.get("vplan_output_file")

    if not vplan_output_file:
        return {
            "langsmith_summary": summary,
            "langsmith_log_file": None,
        }

    log_file = save_usage_log(
        output_file=Path(vplan_output_file),
        logs_dir=USAGE_LOGS_DIR,
        trace_ids={
            "vplan_trace_id": state.get("vplan_trace_id"),
            "edge_case_trace_id": state.get("edge_case_trace_id"),
        },
        usage_summary=summary,
    )

    usage_reports = generate_usage_reports()

    return {
        "langsmith_summary": summary,
        "langsmith_log_file": str(log_file),
        "usage_reports": usage_reports,
    }


def save_workflow_image(chain) -> None:
    try:
        image_bytes = chain.get_graph().draw_mermaid_png()
        WORKFLOW_IMAGE_PATH.write_bytes(image_bytes)
        print(f"Workflow image saved to {WORKFLOW_IMAGE_PATH}")

    except Exception as error:
        print(f"Could not save workflow image: {error}")


def build_workflow():
    workflow = StateGraph(GraphState)

    workflow.add_node("vplan_output", vplan_node)
    workflow.add_node("edge_cases_output", edge_case_node)
    workflow.add_node("usage_summary", usage_summary_node)

    workflow.add_edge(START, "vplan_output")
    workflow.add_edge(START, "edge_cases_output")

    workflow.add_edge("vplan_output", "usage_summary")
    workflow.add_edge("edge_cases_output", "usage_summary")

    workflow.add_edge("usage_summary", END)

    chain = workflow.compile()

    print("Compiled agents")

    save_workflow_image(chain)

    return chain