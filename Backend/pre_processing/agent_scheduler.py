from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from Backend.agents.edge_case_agent import edge_case_agent_call
from Backend.agents.vplan_category_agent import categorise_vplan
from Backend.agents.vplan_generator_agent import v_plan_agent_call
from Backend.config import (
    LANGSMITH_LOGS_DIR as USAGE_LOGS_DIR,
    WORKFLOW_IMAGE_DIR,
)
from Backend.post_processing.analyse_usage_logs import generate_usage_reports
from Backend.post_processing.usage_logger import aggregate_usage, save_usage_log
from Backend.pre_processing.data_class import GraphState
from Backend.pre_processing.preprocess_requirements import (
    preprocess_requirements_file,
)
from Backend.report_generation.blocked_test_report_generator import (
    export_blocked_test_report,
)
from Backend.report_generation.traceability_record_generator import (
    export_requirement_test_links,
)

load_dotenv()

WORKFLOW_IMAGE_PATH = WORKFLOW_IMAGE_DIR / "vplan-architecture.png"


def preprocess_node(state: GraphState) -> dict:
    started = perf_counter()

    original_file = state["requirements_file"]
    preprocessed_file = preprocess_requirements_file(original_file)

    print(f"Preprocessing took {perf_counter() - started:.2f} seconds.")

    return {
        "original_requirements_file": original_file,
        "requirements_file": str(preprocessed_file),
        "preprocessed_requirements_file": str(preprocessed_file),
    }


def edge_case_node(
    state: GraphState,
) -> dict:
    result = edge_case_agent_call(state["requirements_file"])

    print(
        "Edge-case node returned:",
        result.keys(),
    )

    print(
        "Weak words file:",
        result.get("weak_words_file"),
    )

    return result


def vplan_node(state: GraphState) -> dict:
    started = perf_counter()

    result = v_plan_agent_call(
        reqs=state["requirements_file"],
        edge_cases=state.get("edge_cases", {}),
    )

    print(f"vPlan generation took " f"{perf_counter() - started:.2f} seconds.")

    return result


def category_node(state: GraphState) -> dict:
    vplan_output_file = state.get("vplan_output_file")

    if not vplan_output_file:
        raise ValueError(
            "Cannot categorise the vPlan because " "'vplan_output_file' is missing."
        )

    # Use the original uploaded requirements file for human-facing metadata.
    metadata_requirements_file = state.get(
        "original_requirements_file",
        state["requirements_file"],
    )

    categorised_file, category_usage, category_trace_id = categorise_vplan(
        vplan_file=vplan_output_file,
        requirements_file=metadata_requirements_file,
    )

    return {
        "vplan_output_file": str(categorised_file),
        "category_usage": category_usage,
        "category_trace_id": category_trace_id,
    }


def requirement_test_links_node(state: GraphState) -> dict:
    vplan_output_file = state.get("vplan_output_file")

    if not vplan_output_file:
        return {"requirement_test_links_file": None}

    csv_file = export_requirement_test_links(Path(vplan_output_file))

    return {
        "requirement_test_links_file": str(csv_file),
    }


def blocked_test_report_node(state: GraphState) -> dict:
    vplan_output_file = state.get("vplan_output_file")
    edge_case_output_file = state.get("edge_case_output_file")

    if not vplan_output_file or not edge_case_output_file:
        return {"blocked_test_report_file": None}

    report_file = export_blocked_test_report(
        vplan_file=Path(vplan_output_file),
        edge_case_file=Path(edge_case_output_file),
    )

    return {
        "blocked_test_report_file": str(report_file),
    }


def usage_summary_node(state: GraphState) -> dict:
    vplan_usage = state.get("vplan_usage", {})
    edge_case_usage = state.get("edge_case_usage", {})
    category_usage = state.get("category_usage", {})

    summary = aggregate_usage(
        vplan_usage,
        edge_case_usage,
        category_usage,
    )

    vplan_output_file = state.get("vplan_output_file")

    if not vplan_output_file:
        return {
            "langsmith_summary": summary,
            "langsmith_log_file": None,
            "usage_reports": {},
        }

    log_file = save_usage_log(
        output_file=Path(vplan_output_file),
        logs_dir=USAGE_LOGS_DIR,
        trace_ids={
            "vplan_trace_id": state.get("vplan_trace_id"),
            "edge_case_trace_id": state.get("edge_case_trace_id"),
            "category_trace_id": state.get("category_trace_id"),
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
    # The graph only changes when the code changes, so do not redraw it
    # for every API request.
    if WORKFLOW_IMAGE_PATH.exists():
        return

    try:
        WORKFLOW_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        image_bytes = chain.get_graph().draw_mermaid_png()
        WORKFLOW_IMAGE_PATH.write_bytes(image_bytes)

        print(f"Workflow image saved to {WORKFLOW_IMAGE_PATH}")

    except Exception as error:
        print(f"Could not save workflow image: {error}")


def build_workflow():
    workflow = StateGraph(GraphState)

    workflow.add_node(
        "preprocess_requirements",
        preprocess_node,
    )
    workflow.add_node(
        "edge_case_analyser",
        edge_case_node,
    )
    workflow.add_node(
        "vplan_generator",
        vplan_node,
    )
    workflow.add_node(
        "categorise_vplan",
        category_node,
    )
    workflow.add_node(
        "requirement_test_links",
        requirement_test_links_node,
    )
    workflow.add_node(
        "blocked_test_report",
        blocked_test_report_node,
    )
    workflow.add_node(
        "usage_summary",
        usage_summary_node,
    )

    workflow.add_edge(START, "preprocess_requirements")
    workflow.add_edge(
        "preprocess_requirements",
        "edge_case_analyser",
    )
    workflow.add_edge(
        "edge_case_analyser",
        "vplan_generator",
    )
    workflow.add_edge(
        "vplan_generator",
        "categorise_vplan",
    )
    workflow.add_edge(
        "categorise_vplan",
        "requirement_test_links",
    )
    workflow.add_edge(
        "categorise_vplan",
        "blocked_test_report",
    )

    # A list edge is a join: usage_summary waits for both report nodes.
    # Two separate edges can cause the summary node to be scheduled twice.
    workflow.add_edge(
        [
            "requirement_test_links",
            "blocked_test_report",
        ],
        "usage_summary",
    )

    workflow.add_edge("usage_summary", END)

    chain = workflow.compile()

    print("Compiled agents")
    save_workflow_image(chain)

    return chain
