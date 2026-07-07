import json
from decimal import Decimal
from pathlib import Path

import pytest

from Backend.post_processing import usage_logger as usage

# ---------------------------------------------------------------------------
# calculate_cost
# ---------------------------------------------------------------------------


def test_calculate_cost_for_known_model_gpt_5_5():
    result = usage.calculate_cost(
        model_name="gpt-5.5",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    assert result == Decimal("35.00")


def test_calculate_cost_for_known_model_gpt_5_4():
    result = usage.calculate_cost(
        model_name="gpt-5.4",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    assert result == Decimal("17.50")


def test_calculate_cost_for_known_model_gpt_5_4_mini():
    result = usage.calculate_cost(
        model_name="gpt-5.4-mini",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    assert result == Decimal("5.25")


def test_calculate_cost_for_partial_token_usage():
    result = usage.calculate_cost(
        model_name="gpt-5.4",
        input_tokens=500_000,
        output_tokens=250_000,
    )

    assert result == Decimal("5.000")


def test_calculate_cost_returns_zero_for_unknown_model():
    result = usage.calculate_cost(
        model_name="unknown-model",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    assert result == Decimal("0")


def test_calculate_cost_returns_zero_for_zero_tokens():
    result = usage.calculate_cost(
        model_name="gpt-5.4",
        input_tokens=0,
        output_tokens=0,
    )

    assert result == Decimal("0.00")


# ---------------------------------------------------------------------------
# normalise_usage
# ---------------------------------------------------------------------------


def test_normalise_usage_uses_calculated_cost_for_known_model():
    result = usage.normalise_usage(
        agent_name="vplan_generator",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        total_tokens=2_000_000,
        total_cost=999.99,
        model_name="gpt-5.4",
    )

    assert result == {
        "agent_name": "vplan_generator",
        "model_name": "gpt-5.4",
        "prompt_tokens": 1_000_000,
        "completion_tokens": 1_000_000,
        "total_tokens": 2_000_000,
        "total_cost": "17.50",
    }


def test_normalise_usage_falls_back_to_callback_cost_for_unknown_model():
    result = usage.normalise_usage(
        agent_name="edge_case_agent",
        input_tokens=1_000,
        output_tokens=2_000,
        total_tokens=3_000,
        total_cost=0.123,
        model_name="unknown-model",
    )

    assert result == {
        "agent_name": "edge_case_agent",
        "model_name": "unknown-model",
        "prompt_tokens": 1_000,
        "completion_tokens": 2_000,
        "total_tokens": 3_000,
        "total_cost": "0.123",
    }


def test_normalise_usage_accepts_string_callback_cost():
    result = usage.normalise_usage(
        agent_name="edge_case_agent",
        input_tokens=1_000,
        output_tokens=2_000,
        total_tokens=3_000,
        total_cost="0.456",
        model_name="unknown-model",
    )

    assert result["total_cost"] == "0.456"


def test_normalise_usage_treats_none_callback_cost_as_zero_for_unknown_model():
    result = usage.normalise_usage(
        agent_name="edge_case_agent",
        input_tokens=1_000,
        output_tokens=2_000,
        total_tokens=3_000,
        total_cost=None,
        model_name="unknown-model",
    )

    assert result["total_cost"] == "0"


def test_normalise_usage_uses_calculated_cost_even_if_callback_cost_is_zero():
    result = usage.normalise_usage(
        agent_name="vplan_generator",
        input_tokens=1_000_000,
        output_tokens=0,
        total_tokens=1_000_000,
        total_cost=0,
        model_name="gpt-5.5",
    )

    assert result["total_cost"] == "5.00"


# ---------------------------------------------------------------------------
# aggregate_usage
# ---------------------------------------------------------------------------


def test_aggregate_usage_sums_multiple_usage_items():
    first_usage = {
        "agent_name": "vplan_generator",
        "model_name": "gpt-5.4",
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
        "total_cost": "0.01",
    }

    second_usage = {
        "agent_name": "edge_case_agent",
        "model_name": "gpt-5.4",
        "prompt_tokens": 50,
        "completion_tokens": 75,
        "total_tokens": 125,
        "total_cost": "0.02",
    }

    result = usage.aggregate_usage(first_usage, second_usage)

    assert result == {
        "prompt_tokens": 150,
        "completion_tokens": 275,
        "total_tokens": 425,
        "total_cost": "0.03",
        "agents": [first_usage, second_usage],
    }


def test_aggregate_usage_skips_empty_usage_items():
    usage_item = {
        "agent_name": "vplan_generator",
        "model_name": "gpt-5.4",
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
        "total_cost": "0.01",
    }

    result = usage.aggregate_usage({}, usage_item, None)

    assert result == {
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
        "total_cost": "0.01",
        "agents": [usage_item],
    }


def test_aggregate_usage_returns_zero_summary_for_no_items():
    result = usage.aggregate_usage()

    assert result == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "total_cost": "0",
        "agents": [],
    }


def test_aggregate_usage_handles_missing_token_fields():
    usage_item = {
        "agent_name": "vplan_generator",
        "model_name": "gpt-5.4",
        "total_cost": "0.01",
    }

    result = usage.aggregate_usage(usage_item)

    assert result == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "total_cost": "0.01",
        "agents": [usage_item],
    }


def test_aggregate_usage_handles_none_token_values():
    usage_item = {
        "agent_name": "vplan_generator",
        "model_name": "gpt-5.4",
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "total_cost": None,
    }

    result = usage.aggregate_usage(usage_item)

    assert result == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "total_cost": "0",
        "agents": [usage_item],
    }


def test_aggregate_usage_casts_numeric_strings_to_ints():
    usage_item = {
        "agent_name": "vplan_generator",
        "model_name": "gpt-5.4",
        "prompt_tokens": "100",
        "completion_tokens": "200",
        "total_tokens": "300",
        "total_cost": "0.01",
    }

    result = usage.aggregate_usage(usage_item)

    assert result["prompt_tokens"] == 100
    assert result["completion_tokens"] == 200
    assert result["total_tokens"] == 300
    assert result["total_cost"] == "0.01"


# ---------------------------------------------------------------------------
# append_to_master_usage_file
# ---------------------------------------------------------------------------


def test_append_to_master_usage_file_creates_master_file(tmp_path):
    run_record = {
        "timestamp": "2026-07-06T12:00:00",
        "output_file": "generated-vplan.json",
        "summary": {
            "total_tokens": 100,
        },
    }

    result = usage.append_to_master_usage_file(tmp_path, run_record)

    assert result == tmp_path / "all_usage_runs.json"
    assert result.exists()

    saved_data = json.loads(result.read_text(encoding="utf-8"))

    assert saved_data == [run_record]


def test_append_to_master_usage_file_appends_to_existing_file(tmp_path):
    master_file = tmp_path / "all_usage_runs.json"

    existing_record = {
        "timestamp": "2026-07-06T12:00:00",
        "output_file": "first.json",
    }

    new_record = {
        "timestamp": "2026-07-06T12:05:00",
        "output_file": "second.json",
    }

    master_file.write_text(
        json.dumps([existing_record], indent=2),
        encoding="utf-8",
    )

    result = usage.append_to_master_usage_file(tmp_path, new_record)

    saved_data = json.loads(result.read_text(encoding="utf-8"))

    assert saved_data == [existing_record, new_record]


def test_append_to_master_usage_file_raises_for_malformed_existing_master_file(
    tmp_path,
):
    master_file = tmp_path / "all_usage_runs.json"
    master_file.write_text("{ bad json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        usage.append_to_master_usage_file(
            tmp_path,
            {
                "timestamp": "2026-07-06T12:00:00",
            },
        )


# ---------------------------------------------------------------------------
# save_usage_log
# ---------------------------------------------------------------------------


def test_save_usage_log_creates_log_file(tmp_path):
    output_file = tmp_path / "generated-vplan.json"
    output_file.write_text("{}", encoding="utf-8")

    logs_dir = tmp_path / "logs"

    usage_summary = {
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
        "total_cost": "0.01",
        "agents": [],
    }

    trace_ids = {
        "vplan_trace_id": "trace-vplan",
        "edge_case_trace_id": "trace-edge",
    }

    result = usage.save_usage_log(
        output_file=output_file,
        logs_dir=logs_dir,
        trace_ids=trace_ids,
        usage_summary=usage_summary,
    )

    assert result == logs_dir / "generated-vplan_usage_log.json"
    assert result.exists()


def test_save_usage_log_writes_expected_log_data(tmp_path):
    output_file = tmp_path / "generated-vplan.json"
    output_file.write_text("{}", encoding="utf-8")

    logs_dir = tmp_path / "logs"

    usage_summary = {
        "prompt_tokens": 100,
        "completion_tokens": 200,
        "total_tokens": 300,
        "total_cost": "0.01",
        "agents": [],
    }

    trace_ids = {
        "vplan_trace_id": "trace-vplan",
        "edge_case_trace_id": None,
    }

    log_file = usage.save_usage_log(
        output_file=output_file,
        logs_dir=logs_dir,
        trace_ids=trace_ids,
        usage_summary=usage_summary,
    )

    saved_data = json.loads(log_file.read_text(encoding="utf-8"))

    assert saved_data["output_file"] == "generated-vplan.json"
    assert saved_data["trace_ids"] == trace_ids
    assert saved_data["summary"] == usage_summary
    assert "timestamp" in saved_data


def test_save_usage_log_creates_logs_dir_if_missing(tmp_path):
    output_file = tmp_path / "generated-vplan.json"
    output_file.write_text("{}", encoding="utf-8")

    logs_dir = tmp_path / "missing-logs-dir"

    assert not logs_dir.exists()

    usage.save_usage_log(
        output_file=output_file,
        logs_dir=logs_dir,
        trace_ids={},
        usage_summary={},
    )

    assert logs_dir.exists()
    assert logs_dir.is_dir()


def test_save_usage_log_appends_to_master_usage_file(tmp_path):
    output_file = tmp_path / "generated-vplan.json"
    output_file.write_text("{}", encoding="utf-8")

    logs_dir = tmp_path / "logs"

    first_log = usage.save_usage_log(
        output_file=output_file,
        logs_dir=logs_dir,
        trace_ids={"vplan_trace_id": "first"},
        usage_summary={"total_tokens": 100},
    )

    second_log = usage.save_usage_log(
        output_file=output_file,
        logs_dir=logs_dir,
        trace_ids={"vplan_trace_id": "second"},
        usage_summary={"total_tokens": 200},
    )

    master_file = logs_dir / "all_usage_runs.json"
    master_data = json.loads(master_file.read_text(encoding="utf-8"))

    assert first_log == second_log
    assert first_log.name == "generated-vplan_usage_log.json"

    assert len(master_data) == 2
    assert master_data[0]["trace_ids"] == {"vplan_trace_id": "first"}
    assert master_data[1]["trace_ids"] == {"vplan_trace_id": "second"}


def test_save_usage_log_overwrites_same_output_file_log_but_keeps_master_history(
    tmp_path,
):
    output_file = tmp_path / "generated-vplan.json"
    output_file.write_text("{}", encoding="utf-8")

    logs_dir = tmp_path / "logs"

    log_file = usage.save_usage_log(
        output_file=output_file,
        logs_dir=logs_dir,
        trace_ids={"vplan_trace_id": "first"},
        usage_summary={"total_tokens": 100},
    )

    log_file = usage.save_usage_log(
        output_file=output_file,
        logs_dir=logs_dir,
        trace_ids={"vplan_trace_id": "second"},
        usage_summary={"total_tokens": 200},
    )

    latest_log_data = json.loads(log_file.read_text(encoding="utf-8"))
    master_data = json.loads(
        (logs_dir / "all_usage_runs.json").read_text(encoding="utf-8")
    )

    assert latest_log_data["trace_ids"] == {"vplan_trace_id": "second"}
    assert latest_log_data["summary"] == {"total_tokens": 200}

    assert len(master_data) == 2
    assert master_data[0]["summary"] == {"total_tokens": 100}
    assert master_data[1]["summary"] == {"total_tokens": 200}
