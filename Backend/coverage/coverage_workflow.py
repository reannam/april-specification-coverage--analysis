from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
from typing import Any, TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from Backend.coverage.coverage_status_verifier import run_coverage_status_verifier
from Backend.coverage.requirement_mapping import run_requirement_mapping_coverage
from Backend.coverage.traceability_coverage import run_traceability_coverage
from Backend.coverage.full_vs_partial_coverage import run_full_vs_partial_coverage
from Backend.coverage.ambiguity_blocked_coverage import run_ambiguity_blocked_coverage
from Backend.coverage.orphan_vplan_item_rate import run_orphan_vplan_item_rate
from Backend.coverage.granularity_adequacy import run_granularity_adequacy
from Backend.coverage.testability_coverage import run_testability_coverage
from Backend.coverage.final_coverage_report import run_final_coverage_report

from Backend.post_processing.usage_logger import aggregate_usage, save_usage_log
from Backend.post_processing.analyse_usage_logs import generate_usage_reports

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"

COVERAGE_STATUS_DIR = OUTPUT_DIR / "coverage_status"
COVERAGE_STATUS_DIR.mkdir(parents=True, exist_ok=True)

FINAL_COVERAGE_DIR = OUTPUT_DIR / "final_coverage_report"
FINAL_COVERAGE_DIR.mkdir(parents=True, exist_ok=True)

USAGE_LOGS_DIR = OUTPUT_DIR / "langsmith_logs"
USAGE_LOGS_DIR.mkdir(parents=True, exist_ok=True)

WORKFLOW_IMAGE_PATH = OUTPUT_DIR / "coverage-architecture.png"


class CoverageWorkflowState(TypedDict):
    requirements_file: str
    vplan_file: str
    edge_case_file: str
    weak_words_file: str

    coverage_status_file: str

    requirement_mapping_result: dict[str, Any]
    full_vs_partial_result: dict[str, Any]
    traceability_result: dict[str, Any]
    ambiguity_blocked_result: dict[str, Any]
    orphan_rate_result: dict[str, Any]
    granularity_result: dict[str, Any]
    testability_result: dict[str, Any]

    final_coverage_report: dict[str, Any]
    final_coverage_output_files: dict[str, str]

    coverage_status_usage: dict[str, Any]
    granularity_usage: dict[str, Any]
    testability_usage: dict[str, Any]
    total_usage: dict[str, Any]
    usage_report_files: dict[str, str]


def validate_input_paths_node(state: CoverageWorkflowState) -> dict[str, Any]:
    required_paths = [
        "requirements_file",
        "vplan_file",
        "edge_case_file",
        "weak_words_file",
    ]

    for key in required_paths:
        value = state.get(key)

        if not value:
            raise ValueError(
                f"Coverage workflow missing required input path: {key}. "
                f"Current state keys: {list(state.keys())}"
            )

        if not Path(value).exists():
            raise FileNotFoundError(
                f"Coverage workflow input path does not exist for {key}: {value}"
            )

    return {}


def coverage_status_node(state: CoverageWorkflowState) -> dict[str, Any]:
    output_file = COVERAGE_STATUS_DIR / "verified_coverage_status_example.json"

    result = run_coverage_status_verifier(
        spec_file=state["requirements_file"],
        vplan_file=state["vplan_file"],
        edge_case_file=state["edge_case_file"],
        weak_words_file=state["weak_words_file"],
        output_file=output_file,
    )

    if isinstance(result, dict):
        coverage_status_file = result.get("coverage_status_file", str(output_file))
        coverage_status_usage = result.get(
            "usage",
            result.get("coverage_status_usage", {}),
        )
    else:
        coverage_status_file = str(result)
        coverage_status_usage = {}

    return {
        "coverage_status_file": coverage_status_file,
        "coverage_status_usage": coverage_status_usage,
    }


def requirement_mapping_node(state: CoverageWorkflowState) -> dict[str, Any]:
    result = run_requirement_mapping_coverage(
        spec_file=state["requirements_file"],
        vplan_file=state["vplan_file"],
    )

    return {
        "requirement_mapping_result": result,
    }


def full_vs_partial_node(state: CoverageWorkflowState) -> dict[str, Any]:
    result = run_full_vs_partial_coverage(
        coverage_file=state["coverage_status_file"],
    )

    return {
        "full_vs_partial_result": result,
    }


def traceability_node(state: CoverageWorkflowState) -> dict[str, Any]:
    result = run_traceability_coverage(
        vplan_file=state["vplan_file"],
    )

    return {
        "traceability_result": result,
    }


def ambiguity_blocked_node(state: CoverageWorkflowState) -> dict[str, Any]:
    result = run_ambiguity_blocked_coverage(
        spec_file=state["requirements_file"],
        coverage_file=state["coverage_status_file"],
    )

    return {
        "ambiguity_blocked_result": result,
    }


def orphan_rate_node(state: CoverageWorkflowState) -> dict[str, Any]:
    result = run_orphan_vplan_item_rate(
        spec_file=state["requirements_file"],
        vplan_file=state["vplan_file"],
    )

    return {
        "orphan_rate_result": result,
    }


def granularity_node(state: CoverageWorkflowState) -> dict[str, Any]:
    result = run_granularity_adequacy(
        spec_file=state["requirements_file"],
        vplan_file=state["vplan_file"],
    )

    usage = {}

    if isinstance(result, dict):
        usage = result.get("usage", result.get("granularity_usage", {}))

    return {
        "granularity_result": result,
        "granularity_usage": usage,
    }


def testability_node(state: CoverageWorkflowState) -> dict[str, Any]:
    result = run_testability_coverage(
        spec_file=state["requirements_file"],
        vplan_file=state["vplan_file"],
    )

    usage = {}

    if isinstance(result, dict):
        usage = result.get("usage", result.get("testability_usage", {}))

    return {
        "testability_result": result,
        "testability_usage": usage,
    }


def final_report_node(state: CoverageWorkflowState) -> dict[str, Any]:
    result = run_final_coverage_report(
        spec_file=state["requirements_file"],
        vplan_file=state["vplan_file"],
        coverage_file=state["coverage_status_file"],
        output_dir=FINAL_COVERAGE_DIR,
    )

    if not isinstance(result, dict):
        return {
            "final_coverage_report": {},
            "final_coverage_output_files": {},
        }

    report = dict(result.get("report", {}))
    output_files = dict(result.get("output_files", {}))

    granularity_result = state.get(
        "granularity_result",
        {},
    )

    if granularity_result:
        granularity_score = float(
            granularity_result.get(
                "granularity_adequacy",
                0,
            )
            or 0
        )

        coverage_percentages = dict(report.get("coverage_percentages", {}))
        coverage_percentages["granularity_adequacy"] = granularity_score
        report["coverage_percentages"] = coverage_percentages

        coverage_summary = dict(report.get("coverage_summary", {}))
        coverage_summary.update(
            {
                "granularity_mapped_requirements": (
                    granularity_result.get(
                        "mapped_requirements",
                        0,
                    )
                ),
                "granularity_suitable_detail": (
                    granularity_result.get(
                        "requirements_covered_at_suitable_detail",
                        0,
                    )
                ),
                "granularity_not_mapped": (
                    granularity_result.get(
                        "requirements_not_mapped",
                        0,
                    )
                ),
            }
        )
        report["coverage_summary"] = coverage_summary
        report["granularity_adequacy"] = granularity_result

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        granularity_output_file = (
            FINAL_COVERAGE_DIR / f"granularity_adequacy_{timestamp}.json"
        )
        with granularity_output_file.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                granularity_result,
                file,
                indent=2,
                ensure_ascii=False,
            )

        output_files["granularity_adequacy_report"] = str(granularity_output_file)

        final_report_file = (
            FINAL_COVERAGE_DIR / f"final_coverage_report_{timestamp}.json"
        )
        with final_report_file.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                report,
                file,
                indent=2,
                ensure_ascii=False,
            )

        output_files["final_coverage_report"] = str(final_report_file)

    return {
        "final_coverage_report": report,
        "final_coverage_output_files": output_files,
    }


def usage_summary_node(state: CoverageWorkflowState) -> dict[str, Any]:
    usage_items = [
        state.get("coverage_status_usage", {}),
        state.get("granularity_usage", {}),
        state.get("testability_usage", {}),
    ]

    total_usage = aggregate_usage(*usage_items)

    usage_log_file = save_usage_log(
        output_file=Path("coverage_workflow.json"),
        logs_dir=USAGE_LOGS_DIR,
        trace_ids={
            "coverage_status": None,
            "granularity": None,
            "testability": None,
        },
        usage_summary=total_usage,
    )

    usage_report_files = generate_usage_reports()

    return {
        "total_usage": total_usage,
        "usage_report_files": usage_report_files,
    }


def save_workflow_image(chain) -> None:
    if WORKFLOW_IMAGE_PATH.exists():
        return

    try:
        image_bytes = chain.get_graph().draw_mermaid_png()
        WORKFLOW_IMAGE_PATH.write_bytes(image_bytes)
        print(f"Workflow image saved to {WORKFLOW_IMAGE_PATH}")

    except Exception as error:
        print(f"Could not save workflow image: {error}")


def build_coverage_workflow():
    graph = StateGraph(CoverageWorkflowState)

    graph.add_node("validate_input_paths", validate_input_paths_node)

    graph.add_node("coverage_status_verifier", coverage_status_node)

    graph.add_node("requirement_mapping", requirement_mapping_node)
    graph.add_node("full_vs_partial", full_vs_partial_node)
    graph.add_node("traceability", traceability_node)
    graph.add_node("ambiguity_blocked", ambiguity_blocked_node)
    graph.add_node("orphan_rate", orphan_rate_node)
    graph.add_node("granularity_adequacy", granularity_node)
    graph.add_node("testability_coverage", testability_node)

    graph.add_node("final_coverage_report", final_report_node)
    graph.add_node("usage_summary", usage_summary_node)

    graph.add_edge(START, "validate_input_paths")
    graph.add_edge("validate_input_paths", "coverage_status_verifier")

    graph.add_edge("coverage_status_verifier", "requirement_mapping")
    graph.add_edge("coverage_status_verifier", "full_vs_partial")
    graph.add_edge("coverage_status_verifier", "traceability")
    graph.add_edge("coverage_status_verifier", "ambiguity_blocked")
    graph.add_edge("coverage_status_verifier", "orphan_rate")
    graph.add_edge("coverage_status_verifier", "granularity_adequacy")
    graph.add_edge("coverage_status_verifier", "testability_coverage")

    graph.add_edge(
        [
            "requirement_mapping",
            "full_vs_partial",
            "traceability",
            "ambiguity_blocked",
            "orphan_rate",
            "granularity_adequacy",
            "testability_coverage",
        ],
        "final_coverage_report",
    )

    graph.add_edge("final_coverage_report", "usage_summary")
    graph.add_edge("usage_summary", END)

    chain = graph.compile()

    print("Compiled agents")

    save_workflow_image(chain)

    return chain


coverage_workflow = build_coverage_workflow()


def run_coverage_workflow(
    requirements_file: str,
    vplan_file: str,
    edge_case_file: str,
    weak_words_file: str,
) -> dict[str, Any]:
    return coverage_workflow.invoke(
        {
            "requirements_file": requirements_file,
            "vplan_file": vplan_file,
            "edge_case_file": edge_case_file,
            "weak_words_file": weak_words_file,
        }
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run coverage workflow using existing generated files."
    )

    parser.add_argument(
        "--requirements-file",
        required=True,
        help="Path to extracted requirements/spec JSON file.",
    )

    parser.add_argument(
        "--vplan-file",
        required=True,
        help="Path to existing generated vPlan JSON file.",
    )

    parser.add_argument(
        "--edge-case-file",
        required=True,
        help="Path to existing generated edge-case JSON file.",
    )

    parser.add_argument(
        "--weak-words-file",
        required=True,
        help="Path to existing generated weak-words JSON file.",
    )

    args = parser.parse_args()

    result = run_coverage_workflow(
        requirements_file=args.requirements_file,
        vplan_file=args.vplan_file,
        edge_case_file=args.edge_case_file,
        weak_words_file=args.weak_words_file,
    )

    print("\nCoverage workflow complete.")
    print("---------------------------")
    print(f"requirements file:         {result.get('requirements_file')}")
    print(f"vPlan file:                {result.get('vplan_file')}")
    print(f"edge case file:            {result.get('edge_case_file')}")
    print(f"weak words file:           {result.get('weak_words_file')}")
    print(f"coverage status file:      {result.get('coverage_status_file')}")

    output_files = result.get("final_coverage_output_files", {})
    if output_files:
        print("\nFinal coverage output files:")
        for label, file_path in output_files.items():
            print(f"{label}: {file_path}")

    if result.get("total_usage"):
        print("\nTotal usage:")
        print(result["total_usage"])
