from pathlib import Path
import json

import pytest

from Backend.pre_processing import agent_scheduler as scheduler


@pytest.fixture
def workflow_state(tmp_path: Path) -> dict:
    requirements_file = tmp_path / "requirements.json"
    requirements_file.write_text(
        json.dumps(
            {
                "requirements": [
                    {
                        "id": "REQ_I2C_001",
                        "description": "The controller must operate in normal mode.",
                        "text": "The controller shall operate at 100 Kbps.",
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "requirements_file": str(requirements_file),
    }


@pytest.fixture
def workflow_state_with_outputs(tmp_path: Path) -> dict:
    vplan_file = tmp_path / "generated-vplan.json"
    edge_case_file = tmp_path / "generated-edge-cases.json"

    vplan_file.write_text(
        json.dumps(
            {
                "feature_list": [
                    {
                        "test_id": "TEST_REQ_I2C_001_001",
                        "requirement_id": "REQ_I2C_001",
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    edge_case_file.write_text(
        json.dumps(
            {"edge_cases": []},
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "requirements_file": str(tmp_path / "requirements.json"),
        "vplan_output_file": str(vplan_file),
        "edge_case_output_file": str(edge_case_file),
        "vplan_usage": {
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        },
        "edge_case_usage": {
            "input_tokens": 5,
            "output_tokens": 10,
            "total_tokens": 15,
        },
        "category_usage": {
            "input_tokens": 2,
            "output_tokens": 3,
            "total_tokens": 5,
        },
        "vplan_trace_id": "trace-vplan-123",
        "edge_case_trace_id": "trace-edge-456",
        "category_trace_id": "trace-category-789",
    }


# ---------------------------------------------------------------------------
# preprocess_node
# ---------------------------------------------------------------------------


def test_preprocess_node_returns_original_and_preprocessed_paths(
    workflow_state,
    monkeypatch,
    tmp_path,
):
    preprocessed_file = tmp_path / "preprocessed" / "requirements_only.json"
    preprocessed_file.parent.mkdir(parents=True, exist_ok=True)
    preprocessed_file.write_text("{}", encoding="utf-8")

    def fake_preprocess_requirements_file(original_file):
        assert original_file == workflow_state["requirements_file"]
        return preprocessed_file

    monkeypatch.setattr(
        scheduler,
        "preprocess_requirements_file",
        fake_preprocess_requirements_file,
    )

    result = scheduler.preprocess_node(workflow_state)

    assert result == {
        "original_requirements_file": workflow_state["requirements_file"],
        "requirements_file": str(preprocessed_file),
        "preprocessed_requirements_file": str(preprocessed_file),
    }


# ---------------------------------------------------------------------------
# vplan_node
# ---------------------------------------------------------------------------


def test_vplan_node_calls_vplan_agent_with_requirements_and_edge_cases(
    workflow_state,
    monkeypatch,
):
    workflow_state["edge_cases"] = {
        "edge_cases": [
            {
                "edge_case_id": "EDGE_REQ_I2C_001_001",
                "requirement_id": "REQ_I2C_001",
            }
        ]
    }

    expected_result = {
        "vplan": {"feature_list": []},
        "vplan_output_file": "generated-vplan.json",
        "vplan_usage": {"total_tokens": 100},
        "vplan_trace_id": "trace-vplan",
    }

    def fake_v_plan_agent_call(reqs, edge_cases):
        assert reqs == workflow_state["requirements_file"]
        assert edge_cases == workflow_state["edge_cases"]
        return expected_result

    monkeypatch.setattr(
        scheduler,
        "v_plan_agent_call",
        fake_v_plan_agent_call,
    )

    result = scheduler.vplan_node(workflow_state)

    assert result == expected_result


def test_vplan_node_uses_empty_edge_cases_when_missing(
    workflow_state,
    monkeypatch,
):
    expected_result = {"vplan": {"feature_list": []}}

    def fake_v_plan_agent_call(reqs, edge_cases):
        assert reqs == workflow_state["requirements_file"]
        assert edge_cases == {}
        return expected_result

    monkeypatch.setattr(
        scheduler,
        "v_plan_agent_call",
        fake_v_plan_agent_call,
    )

    result = scheduler.vplan_node(workflow_state)

    assert result == expected_result


# ---------------------------------------------------------------------------
# edge_case_node
# ---------------------------------------------------------------------------


def test_edge_case_node_calls_edge_case_agent(
    workflow_state,
    monkeypatch,
):
    expected_result = {
        "edge_cases": {"edge_cases": []},
        "edge_case_output_file": "generated-edge-cases.json",
        "edge_case_usage": {"total_tokens": 50},
        "edge_case_trace_id": "trace-edge",
    }

    def fake_edge_case_agent_call(requirements_file):
        assert requirements_file == workflow_state["requirements_file"]
        return expected_result

    monkeypatch.setattr(
        scheduler,
        "edge_case_agent_call",
        fake_edge_case_agent_call,
    )

    result = scheduler.edge_case_node(workflow_state)

    assert result == expected_result


# ---------------------------------------------------------------------------
# usage_summary_node
# ---------------------------------------------------------------------------


def test_usage_summary_node_returns_summary_without_log_file_when_no_vplan_output(
    workflow_state,
    monkeypatch,
):
    expected_summary = {
        "total_tokens": 45,
        "total_cost": 0.001,
    }

    # Build the exact state needed for this branch rather than relying on
    # any additional fields that may be added to the shared fixture.
    state = {
        "requirements_file": workflow_state["requirements_file"],
    }

    aggregate_calls = []

    def fake_aggregate_usage(
        vplan_usage,
        edge_case_usage,
        category_usage,
    ):
        aggregate_calls.append(
            (
                vplan_usage,
                edge_case_usage,
                category_usage,
            )
        )
        return expected_summary

    def unexpected_save_usage_log(*args, **kwargs):
        raise AssertionError(
            "save_usage_log must not be called without a vPlan output file."
        )

    def unexpected_generate_usage_reports(*args, **kwargs):
        raise AssertionError(
            "generate_usage_reports must not be called without a vPlan output file."
        )

    monkeypatch.setattr(
        scheduler,
        "aggregate_usage",
        fake_aggregate_usage,
    )
    monkeypatch.setattr(
        scheduler,
        "save_usage_log",
        unexpected_save_usage_log,
    )
    monkeypatch.setattr(
        scheduler,
        "generate_usage_reports",
        unexpected_generate_usage_reports,
    )

    result = scheduler.usage_summary_node(state)

    assert aggregate_calls == [
        (
            {},
            {},
            {},
        )
    ]

    assert result["langsmith_summary"] == expected_summary

    # This passes whether the key is absent or explicitly set to None.
    assert result.get("langsmith_log_file") is None

    # Some versions return an empty reports dictionary in this branch.
    assert result.get("usage_reports", {}) == {}


def test_usage_summary_node_saves_usage_log_and_generates_reports(
    workflow_state_with_outputs,
    monkeypatch,
    tmp_path,
):
    expected_summary = {
        "total_tokens": 45,
        "total_cost": 0.001,
    }

    expected_log_file = tmp_path / "usage-log.json"

    expected_usage_reports = {
        "summary_report": "summary.csv",
        "model_report": "model.csv",
    }

    def fake_aggregate_usage(vplan_usage, edge_case_usage, category_usage):
        assert vplan_usage == workflow_state_with_outputs["vplan_usage"]
        assert edge_case_usage == workflow_state_with_outputs["edge_case_usage"]
        assert category_usage == workflow_state_with_outputs["category_usage"]
        return expected_summary

    def fake_save_usage_log(output_file, logs_dir, trace_ids, usage_summary):
        assert output_file == Path(workflow_state_with_outputs["vplan_output_file"])
        assert logs_dir == scheduler.USAGE_LOGS_DIR
        assert trace_ids == {
            "vplan_trace_id": "trace-vplan-123",
            "edge_case_trace_id": "trace-edge-456",
            "category_trace_id": "trace-category-789",
        }
        assert usage_summary == expected_summary
        return expected_log_file

    def fake_generate_usage_reports():
        return expected_usage_reports

    monkeypatch.setattr(
        scheduler,
        "aggregate_usage",
        fake_aggregate_usage,
    )
    monkeypatch.setattr(
        scheduler,
        "save_usage_log",
        fake_save_usage_log,
    )
    monkeypatch.setattr(
        scheduler,
        "generate_usage_reports",
        fake_generate_usage_reports,
    )

    result = scheduler.usage_summary_node(workflow_state_with_outputs)

    assert result == {
        "langsmith_summary": expected_summary,
        "langsmith_log_file": str(expected_log_file),
        "usage_reports": expected_usage_reports,
    }


def test_usage_summary_node_uses_empty_usage_dicts_when_missing(
    workflow_state_with_outputs,
    monkeypatch,
    tmp_path,
):
    workflow_state_with_outputs.pop("vplan_usage")
    workflow_state_with_outputs.pop("edge_case_usage")
    workflow_state_with_outputs.pop("category_usage")

    expected_log_file = tmp_path / "usage-log.json"

    def fake_aggregate_usage(vplan_usage, edge_case_usage, category_usage):
        assert vplan_usage == {}
        assert edge_case_usage == {}
        assert category_usage == {}
        return {"total_tokens": 0}

    def fake_save_usage_log(output_file, logs_dir, trace_ids, usage_summary):
        return expected_log_file

    def fake_generate_usage_reports():
        return {}

    monkeypatch.setattr(scheduler, "aggregate_usage", fake_aggregate_usage)
    monkeypatch.setattr(scheduler, "save_usage_log", fake_save_usage_log)
    monkeypatch.setattr(
        scheduler, "generate_usage_reports", fake_generate_usage_reports
    )

    result = scheduler.usage_summary_node(workflow_state_with_outputs)

    assert result["langsmith_summary"] == {"total_tokens": 0}
    assert result["langsmith_log_file"] == str(expected_log_file)
    assert result["usage_reports"] == {}


# ---------------------------------------------------------------------------
# requirement_test_links_node
# ---------------------------------------------------------------------------


def test_requirement_test_links_node_returns_none_when_no_vplan_output():
    result = scheduler.requirement_test_links_node({})

    assert result == {
        "requirement_test_links_file": None,
    }


def test_requirement_test_links_node_exports_links(
    workflow_state_with_outputs,
    monkeypatch,
    tmp_path,
):
    expected_csv = tmp_path / "requirement-test-links.csv"

    def fake_export_requirement_test_links(vplan_output_file):
        assert vplan_output_file == Path(
            workflow_state_with_outputs["vplan_output_file"]
        )
        return expected_csv

    monkeypatch.setattr(
        scheduler,
        "export_requirement_test_links",
        fake_export_requirement_test_links,
    )

    result = scheduler.requirement_test_links_node(workflow_state_with_outputs)

    assert result == {
        "requirement_test_links_file": str(expected_csv),
    }


# ---------------------------------------------------------------------------
# blocked_test_report_node
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "state",
    [
        {},
        {
            "vplan_output_file": "generated-vplan.json",
        },
        {
            "edge_case_output_file": "generated-edge-cases.json",
        },
    ],
)
def test_blocked_test_report_node_returns_none_when_required_files_missing(state):
    result = scheduler.blocked_test_report_node(state)

    assert result == {
        "blocked_test_report_file": None,
    }


def test_blocked_test_report_node_exports_report(
    workflow_state_with_outputs,
    monkeypatch,
    tmp_path,
):
    expected_report = tmp_path / "blocked-test-report.json"

    def fake_export_blocked_test_report(vplan_file, edge_case_file):
        assert vplan_file == Path(workflow_state_with_outputs["vplan_output_file"])
        assert edge_case_file == Path(
            workflow_state_with_outputs["edge_case_output_file"]
        )
        return expected_report

    monkeypatch.setattr(
        scheduler,
        "export_blocked_test_report",
        fake_export_blocked_test_report,
    )

    result = scheduler.blocked_test_report_node(workflow_state_with_outputs)

    assert result == {
        "blocked_test_report_file": str(expected_report),
    }


# ---------------------------------------------------------------------------
# save_workflow_image
# ---------------------------------------------------------------------------


def test_save_workflow_image_writes_architecture_image(
    monkeypatch,
    tmp_path,
    capsys,
):
    image_path = tmp_path / "architecture.png"

    class FakeGraph:
        def draw_mermaid_png(self):
            return b"fake-png-bytes"

    class FakeChain:
        def get_graph(self):
            return FakeGraph()

    monkeypatch.setattr(
        scheduler,
        "WORKFLOW_IMAGE_PATH",
        image_path,
    )

    scheduler.save_workflow_image(FakeChain())

    captured = capsys.readouterr()

    assert image_path.exists()
    assert image_path.read_bytes() == b"fake-png-bytes"
    assert f"Workflow image saved to {image_path}" in captured.out


def test_save_workflow_image_does_not_raise_when_graph_render_fails():
    class BrokenGraph:
        def draw_mermaid_png(self):
            raise RuntimeError("render failed")

    class BrokenChain:
        def get_graph(self):
            return BrokenGraph()

    # Workflow image generation is best-effort and must not stop the API flow.
    scheduler.save_workflow_image(BrokenChain())


# ---------------------------------------------------------------------------
# build_workflow
# ---------------------------------------------------------------------------


def test_build_workflow_returns_compiled_chain(monkeypatch, capsys):
    saved = {
        "called": False,
    }

    def fake_save_workflow_image(chain):
        saved["called"] = True

    monkeypatch.setattr(
        scheduler,
        "save_workflow_image",
        fake_save_workflow_image,
    )

    chain = scheduler.build_workflow()

    captured = capsys.readouterr()

    assert chain is not None
    assert saved["called"] is True
    assert "Compiled agents" in captured.out


def test_build_workflow_compiled_chain_can_be_invoked_with_patched_nodes(
    workflow_state,
    monkeypatch,
    tmp_path,
):
    """
    This is closer to an integration test of the workflow shape.

    It patches the external side-effect functions so no real agents, LangSmith
    calls, CSV exports, or blocked-test reports are created.
    """
    preprocessed_file = tmp_path / "preprocessed-requirements.json"
    preprocessed_file.write_text("{}", encoding="utf-8")

    def fake_preprocess_requirements_file(original_file):
        return preprocessed_file

    def fake_edge_case_agent_call(requirements_file):
        return {
            "edge_cases": {"edge_cases": []},
            "edge_case_output_file": str(tmp_path / "edge-cases.json"),
            "edge_case_usage": {"total_tokens": 10},
            "edge_case_trace_id": "trace-edge",
        }

    def fake_v_plan_agent_call(reqs, edge_cases):
        vplan_output_file = tmp_path / "vplan.json"
        vplan_output_file.write_text(
            '{"feature_list": []}',
            encoding="utf-8",
        )

        return {
            "vplan": {"feature_list": []},
            "vplan_output_file": str(vplan_output_file),
            "vplan_usage": {"total_tokens": 20},
            "vplan_trace_id": "trace-vplan",
        }

    def fake_category_node(state):
        categorised_vplan_file = tmp_path / "categorised-vplan.json"
        categorised_vplan_file.write_text(
            '{"feature_list": []}',
            encoding="utf-8",
        )

        return {
            "vplan": {"feature_list": []},
            "vplan_output_file": str(categorised_vplan_file),
            "category_usage": {"total_tokens": 5},
            "category_trace_id": "trace-category",
        }

    def fake_export_requirement_test_links(vplan_file):
        return tmp_path / "links.csv"

    def fake_export_blocked_test_report(vplan_file, edge_case_file):
        return tmp_path / "blocked-report.json"

    def fake_aggregate_usage(vplan_usage, edge_case_usage, category_usage):
        assert vplan_usage == {"total_tokens": 20}
        assert edge_case_usage == {"total_tokens": 10}
        assert category_usage == {"total_tokens": 5}
        return {"total_tokens": 35}

    def fake_save_usage_log(output_file, logs_dir, trace_ids, usage_summary):
        return tmp_path / "usage-log.json"

    def fake_generate_usage_reports():
        return {"usage_summary": "ok"}

    monkeypatch.setattr(
        scheduler, "preprocess_requirements_file", fake_preprocess_requirements_file
    )
    monkeypatch.setattr(scheduler, "edge_case_agent_call", fake_edge_case_agent_call)
    monkeypatch.setattr(scheduler, "v_plan_agent_call", fake_v_plan_agent_call)
    monkeypatch.setattr(scheduler, "category_node", fake_category_node)
    monkeypatch.setattr(
        scheduler, "export_requirement_test_links", fake_export_requirement_test_links
    )
    monkeypatch.setattr(
        scheduler, "export_blocked_test_report", fake_export_blocked_test_report
    )
    monkeypatch.setattr(scheduler, "aggregate_usage", fake_aggregate_usage)
    monkeypatch.setattr(scheduler, "save_usage_log", fake_save_usage_log)
    monkeypatch.setattr(
        scheduler, "generate_usage_reports", fake_generate_usage_reports
    )
    monkeypatch.setattr(scheduler, "save_workflow_image", lambda chain: None)

    chain = scheduler.build_workflow()

    result = chain.invoke(workflow_state)

    assert result["original_requirements_file"] == workflow_state["requirements_file"]
    assert result["requirements_file"] == str(preprocessed_file)
    assert result["preprocessed_requirements_file"] == str(preprocessed_file)
    assert result["edge_cases"] == {"edge_cases": []}
    assert result["vplan"] == {"feature_list": []}
    assert result["requirement_test_links_file"] == str(tmp_path / "links.csv")
    assert result["blocked_test_report_file"] == str(tmp_path / "blocked-report.json")
    assert result["category_usage"] == {"total_tokens": 5}
    assert result["category_trace_id"] == "trace-category"
    assert result["langsmith_summary"] == {"total_tokens": 35}
    assert result["langsmith_log_file"] == str(tmp_path / "usage-log.json")
    assert result["usage_reports"] == {"usage_summary": "ok"}
