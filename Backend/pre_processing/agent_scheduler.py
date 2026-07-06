from pathlib import Path

from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv

from Backend.data_class import GraphState
from Backend.agents.edge_case_agent import edge_case_agent_call
from Backend.agents.vplan_generator_agent import v_plan_agent_call
from Backend.usage_logger import aggregate_usage, save_usage_log
from Backend.analyse_usage_logs import generate_usage_reports
from Backend.traceability_record_generator import export_requirement_test_links
from Backend.preprocess_requirements import preprocess_requirements_file
from Backend.blocked_test_report_generator import export_blocked_test_report

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"

USAGE_LOGS_DIR = OUTPUT_DIR / "langsmith_logs"
USAGE_LOGS_DIR.mkdir(parents=True, exist_ok=True)

WORKFLOW_IMAGE_DIR = OUTPUT_DIR / "node_architecture_graph"
WORKFLOW_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

WORKFLOW_IMAGE_PATH = WORKFLOW_IMAGE_DIR / "architecture.png"

def preprocess_node(state: GraphState) -> dict:
    original_file = state["requirements_file"]
    preprocessed_file = preprocess_requirements_file(original_file)

    return {
        "original_requirements_file": original_file,
        "requirements_file": str(preprocessed_file),
        "preprocessed_requirements_file": str(preprocessed_file),
    }


def vplan_node(state: GraphState) -> dict:
    return v_plan_agent_call(
        reqs=state["requirements_file"],
        edge_cases=state.get("edge_cases", {}),
    )


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

def requirement_test_links_node(state: GraphState) -> dict:
    vplan_output_file = state.get("vplan_output_file")

    if not vplan_output_file:
        return {
            "requirement_test_links_file": None,
        }

    csv_file = export_requirement_test_links(Path(vplan_output_file))

    return {
        "requirement_test_links_file": str(csv_file),
    }

def blocked_test_report_node(state: GraphState) -> dict:
    vplan_output_file = state.get("vplan_output_file")
    edge_case_output_file = state.get("edge_case_output_file")

    if not vplan_output_file or not edge_case_output_file:
        return {
            "blocked_test_report_file": None,
        }

    report_file = export_blocked_test_report(
        vplan_file=Path(vplan_output_file),
        edge_case_file=Path(edge_case_output_file),
    )

    return {
        "blocked_test_report_file": str(report_file),
    }

def build_workflow():
    workflow = StateGraph(GraphState)

    workflow.add_node("preprocess_requirements", preprocess_node)
    workflow.add_node("edge_case_analyser", edge_case_node)
    workflow.add_node("vplan_generator", vplan_node)
    workflow.add_node("requirement_test_links", requirement_test_links_node)
    workflow.add_node("blocked_test_report", blocked_test_report_node)
    workflow.add_node("usage_summary", usage_summary_node)

    workflow.add_edge(START, "preprocess_requirements")

    workflow.add_edge("preprocess_requirements", "edge_case_analyser")
    workflow.add_edge("edge_case_analyser", "vplan_generator")

    workflow.add_edge("vplan_generator", "requirement_test_links")
    workflow.add_edge("vplan_generator", "blocked_test_report")

    workflow.add_edge("requirement_test_links", "usage_summary")
    workflow.add_edge("blocked_test_report", "usage_summary")

    workflow.add_edge("usage_summary", END)

    chain = workflow.compile()

    print("Compiled agents")

    save_workflow_image(chain)

    return chain