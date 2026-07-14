import json
from pathlib import Path

import pytest

from Backend.coverage import coverage_workflow as workflow


@pytest.fixture
def input_state(tmp_path):
    state = {}
    for key in ["requirements_file", "vplan_file", "edge_case_file", "weak_words_file"]:
        path = tmp_path / f"{key}.json"
        path.write_text("{}", encoding="utf-8")
        state[key] = str(path)
    return state


def test_validate_input_paths_node_accepts_existing_files(input_state):
    assert workflow.validate_input_paths_node(input_state) == {}


def test_validate_input_paths_node_rejects_missing_key(input_state):
    input_state.pop("vplan_file")

    with pytest.raises(ValueError, match="vplan_file"):
        workflow.validate_input_paths_node(input_state)


def test_validate_input_paths_node_rejects_missing_file(input_state):
    input_state["vplan_file"] = "does-not-exist.json"

    with pytest.raises(FileNotFoundError, match="vplan_file"):
        workflow.validate_input_paths_node(input_state)


def test_coverage_status_node_reads_file_and_usage(input_state, monkeypatch, tmp_path):
    monkeypatch.setattr(workflow, "COVERAGE_STATUS_DIR", tmp_path)

    def fake_run(**kwargs):
        assert kwargs["spec_file"] == input_state["requirements_file"]
        assert (
            kwargs["output_file"] == tmp_path / "verified_coverage_status_example.json"
        )
        return {"coverage_status_file": "verified.json", "usage": {"total_tokens": 4}}

    monkeypatch.setattr(workflow, "run_coverage_status_verifier", fake_run)

    assert workflow.coverage_status_node(input_state) == {
        "coverage_status_file": "verified.json",
        "coverage_status_usage": {"total_tokens": 4},
    }


def test_coverage_status_node_supports_path_return(input_state, monkeypatch):
    monkeypatch.setattr(
        workflow,
        "run_coverage_status_verifier",
        lambda **kwargs: Path("verified.json"),
    )

    assert workflow.coverage_status_node(input_state) == {
        "coverage_status_file": "verified.json",
        "coverage_status_usage": {},
    }


@pytest.mark.parametrize(
    ("node_name", "runner_name", "result_key", "expected_kwargs"),
    [
        (
            "requirement_mapping_node",
            "run_requirement_mapping_coverage",
            "requirement_mapping_result",
            {"spec_file": "requirements_file", "vplan_file": "vplan_file"},
        ),
        (
            "full_vs_partial_node",
            "run_full_vs_partial_coverage",
            "full_vs_partial_result",
            {"coverage_file": "coverage_status_file"},
        ),
        (
            "traceability_node",
            "run_traceability_coverage",
            "traceability_result",
            {"vplan_file": "vplan_file"},
        ),
        (
            "ambiguity_blocked_node",
            "run_ambiguity_blocked_coverage",
            "ambiguity_blocked_result",
            {"spec_file": "requirements_file", "coverage_file": "coverage_status_file"},
        ),
        (
            "orphan_rate_node",
            "run_orphan_vplan_item_rate",
            "orphan_rate_result",
            {"spec_file": "requirements_file", "vplan_file": "vplan_file"},
        ),
    ],
)
def test_simple_metric_nodes(
    monkeypatch, node_name, runner_name, result_key, expected_kwargs
):
    state = {
        "requirements_file": "spec.json",
        "vplan_file": "vplan.json",
        "coverage_status_file": "coverage.json",
    }
    calls = []

    def fake_runner(**kwargs):
        calls.append(kwargs)
        return {"metric": "ok"}

    monkeypatch.setattr(workflow, runner_name, fake_runner)

    result = getattr(workflow, node_name)(state)

    assert result == {result_key: {"metric": "ok"}}
    assert calls == [
        {argument: state[state_key] for argument, state_key in expected_kwargs.items()}
    ]


def test_granularity_and_testability_nodes_extract_usage(monkeypatch):
    state = {"requirements_file": "spec.json", "vplan_file": "vplan.json"}
    monkeypatch.setattr(
        workflow,
        "run_granularity_adequacy",
        lambda **kwargs: {"granularity_adequacy": 80, "usage": {"total_tokens": 2}},
    )
    monkeypatch.setattr(
        workflow,
        "run_testability_coverage",
        lambda **kwargs: {
            "testability_coverage": 90,
            "testability_usage": {"total_tokens": 3},
        },
    )

    granularity = workflow.granularity_node(state)
    testability = workflow.testability_node(state)

    assert granularity["granularity_usage"] == {"total_tokens": 2}
    assert testability["testability_usage"] == {"total_tokens": 3}


def test_final_report_node_handles_non_dict(monkeypatch):
    monkeypatch.setattr(workflow, "run_final_coverage_report", lambda **kwargs: None)

    result = workflow.final_report_node(
        {
            "requirements_file": "spec.json",
            "vplan_file": "vplan.json",
            "coverage_status_file": "coverage.json",
        }
    )

    assert result == {
        "final_coverage_report": {},
        "final_coverage_output_files": {},
    }


def test_final_report_node_merges_granularity(monkeypatch, tmp_path):
    monkeypatch.setattr(workflow, "FINAL_COVERAGE_DIR", tmp_path)
    monkeypatch.setattr(
        workflow,
        "run_final_coverage_report",
        lambda **kwargs: {
            "report": {
                "coverage_percentages": {"weighted_coverage": 50.0},
                "coverage_summary": {"total_spec_items": 2},
            },
            "output_files": {"coverage_summary_file": "summary.json"},
        },
    )

    result = workflow.final_report_node(
        {
            "requirements_file": "spec.json",
            "vplan_file": "vplan.json",
            "coverage_status_file": "coverage.json",
            "granularity_result": {
                "granularity_adequacy": 75,
                "mapped_requirements": 2,
                "requirements_covered_at_suitable_detail": 1,
                "requirements_not_mapped": 1,
            },
        }
    )

    report = result["final_coverage_report"]
    assert report["coverage_percentages"]["granularity_adequacy"] == 75.0
    assert report["coverage_summary"]["granularity_mapped_requirements"] == 2
    assert Path(
        result["final_coverage_output_files"]["granularity_adequacy_report"]
    ).exists()
    assert Path(result["final_coverage_output_files"]["final_coverage_report"]).exists()


def test_usage_summary_node_aggregates_and_generates_reports(monkeypatch, tmp_path):
    calls = {}

    def fake_aggregate(*items):
        calls["items"] = items
        return {"total_tokens": 6}

    def fake_save_usage_log(**kwargs):
        calls["save"] = kwargs
        return tmp_path / "usage.json"

    monkeypatch.setattr(workflow, "aggregate_usage", fake_aggregate)
    monkeypatch.setattr(workflow, "save_usage_log", fake_save_usage_log)
    monkeypatch.setattr(
        workflow, "generate_usage_reports", lambda: {"summary": "summary.csv"}
    )

    result = workflow.usage_summary_node(
        {
            "coverage_status_usage": {"total_tokens": 1},
            "granularity_usage": {"total_tokens": 2},
            "testability_usage": {"total_tokens": 3},
        }
    )

    assert calls["items"] == (
        {"total_tokens": 1},
        {"total_tokens": 2},
        {"total_tokens": 3},
    )
    assert calls["save"]["usage_summary"] == {"total_tokens": 6}
    assert result == {
        "total_usage": {"total_tokens": 6},
        "usage_report_files": {"summary": "summary.csv"},
    }


def test_save_workflow_image_writes_bytes(monkeypatch, tmp_path):
    image_path = tmp_path / "workflow.png"
    monkeypatch.setattr(workflow, "WORKFLOW_IMAGE_PATH", image_path)

    class Graph:
        def draw_mermaid_png(self):
            return b"png"

    class Chain:
        def get_graph(self):
            return Graph()

    workflow.save_workflow_image(Chain())

    assert image_path.read_bytes() == b"png"


def test_save_workflow_image_does_not_overwrite_existing(monkeypatch, tmp_path):
    image_path = tmp_path / "workflow.png"
    image_path.write_bytes(b"old")
    monkeypatch.setattr(workflow, "WORKFLOW_IMAGE_PATH", image_path)

    class Chain:
        def get_graph(self):
            raise AssertionError("should not render")

    workflow.save_workflow_image(Chain())

    assert image_path.read_bytes() == b"old"


def test_run_coverage_workflow_invokes_compiled_workflow(monkeypatch):
    calls = []

    class FakeWorkflow:
        def invoke(self, state):
            calls.append(state)
            return {"done": True}

    monkeypatch.setattr(workflow, "coverage_workflow", FakeWorkflow())

    result = workflow.run_coverage_workflow("spec", "vplan", "edges", "weak")

    assert result == {"done": True}
    assert calls == [
        {
            "requirements_file": "spec",
            "vplan_file": "vplan",
            "edge_case_file": "edges",
            "weak_words_file": "weak",
        }
    ]
