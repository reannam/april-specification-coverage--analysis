import json
from pathlib import Path

import pandas as pd
import pytest

from Backend.post_processing import analyse_usage_logs as analysis


@pytest.fixture
def usage_runs_data() -> list[dict]:
    return [
        {
            "timestamp": "2026-07-06T12:00:00",
            "output_file": "generated-vplan-1.json",
            "summary": {
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "total_tokens": 300,
                "total_cost": "0.01",
                "agents": [
                    {
                        "agent_name": "vplan_generator",
                        "model_name": "gpt-5.4",
                        "prompt_tokens": 70,
                        "completion_tokens": 150,
                        "total_tokens": 220,
                        "total_cost": "0.007",
                    },
                    {
                        "agent_name": "edge_case_agent",
                        "model_name": "gpt-5.4-mini",
                        "prompt_tokens": 30,
                        "completion_tokens": 50,
                        "total_tokens": 80,
                        "total_cost": "0.003",
                    },
                ],
            },
        },
        {
            "timestamp": "2026-07-06T12:05:00",
            "output_file": "generated-vplan-2.json",
            "summary": {
                "prompt_tokens": 50,
                "completion_tokens": 75,
                "total_tokens": 125,
                "total_cost": "0.02",
                "agents": [
                    {
                        "agent_name": "vplan_generator",
                        "model_name": "gpt-5.4",
                        "prompt_tokens": 50,
                        "completion_tokens": 75,
                        "total_tokens": 125,
                        "total_cost": "0.02",
                    },
                ],
            },
        },
    ]


@pytest.fixture
def master_usage_file(tmp_path: Path, usage_runs_data: list[dict]) -> Path:
    file_path = tmp_path / "all_usage_runs.json"
    file_path.write_text(json.dumps(usage_runs_data, indent=2), encoding="utf-8")
    return file_path


@pytest.fixture
def patched_usage_paths(
    tmp_path: Path,
    master_usage_file: Path,
    monkeypatch,
) -> Path:
    charts_dir = tmp_path / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(analysis, "MASTER_USAGE_FILE", master_usage_file)
    monkeypatch.setattr(analysis, "CHARTS_DIR", charts_dir)

    return charts_dir


# ---------------------------------------------------------------------------
# load_usage_data
# ---------------------------------------------------------------------------


def test_load_usage_data_returns_empty_dataframes_when_master_file_missing(
    tmp_path,
    monkeypatch,
):
    missing_file = tmp_path / "missing-all-usage-runs.json"

    monkeypatch.setattr(analysis, "MASTER_USAGE_FILE", missing_file)

    run_df, agent_df = analysis.load_usage_data()

    assert isinstance(run_df, pd.DataFrame)
    assert isinstance(agent_df, pd.DataFrame)
    assert run_df.empty
    assert agent_df.empty


def test_load_usage_data_builds_run_dataframe(patched_usage_paths):
    run_df, agent_df = analysis.load_usage_data()

    assert len(run_df) == 2

    assert list(run_df.columns) == [
        "run_id",
        "timestamp",
        "output_file",
        "models_used",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "total_cost",
    ]

    first_row = run_df.iloc[0]

    assert first_row["run_id"] == 1
    assert first_row["timestamp"] == "2026-07-06T12:00:00"
    assert first_row["output_file"] == "generated-vplan-1.json"
    assert first_row["models_used"] == "gpt-5.4, gpt-5.4-mini"
    assert first_row["prompt_tokens"] == 100
    assert first_row["completion_tokens"] == 200
    assert first_row["total_tokens"] == 300
    assert first_row["total_cost"] == 0.01


def test_load_usage_data_builds_agent_dataframe(patched_usage_paths):
    run_df, agent_df = analysis.load_usage_data()

    assert len(agent_df) == 3

    assert list(agent_df.columns) == [
        "run_id",
        "timestamp",
        "output_file",
        "agent_name",
        "model_name",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "total_cost",
    ]

    first_agent = agent_df.iloc[0]

    assert first_agent["run_id"] == 1
    assert first_agent["agent_name"] == "vplan_generator"
    assert first_agent["model_name"] == "gpt-5.4"
    assert first_agent["prompt_tokens"] == 70
    assert first_agent["completion_tokens"] == 150
    assert first_agent["total_tokens"] == 220
    assert first_agent["total_cost"] == 0.007


def test_load_usage_data_uses_unknown_model_when_agents_empty(tmp_path, monkeypatch):
    master_file = tmp_path / "all_usage_runs.json"
    master_file.write_text(
        json.dumps(
            [
                {
                    "timestamp": "2026-07-06T12:00:00",
                    "output_file": "generated-vplan.json",
                    "summary": {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                        "total_cost": "0.001",
                        "agents": [],
                    },
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(analysis, "MASTER_USAGE_FILE", master_file)

    run_df, agent_df = analysis.load_usage_data()

    assert len(run_df) == 1
    assert run_df.iloc[0]["models_used"] == "Unknown model"
    assert agent_df.empty


def test_load_usage_data_defaults_missing_summary_values(tmp_path, monkeypatch):
    master_file = tmp_path / "all_usage_runs.json"
    master_file.write_text(
        json.dumps(
            [
                {
                    "timestamp": "2026-07-06T12:00:00",
                    "output_file": "generated-vplan.json",
                    "summary": {},
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(analysis, "MASTER_USAGE_FILE", master_file)

    run_df, agent_df = analysis.load_usage_data()

    row = run_df.iloc[0]

    assert row["models_used"] == "Unknown model"
    assert row["prompt_tokens"] == 0
    assert row["completion_tokens"] == 0
    assert row["total_tokens"] == 0
    assert row["total_cost"] == 0.0
    assert agent_df.empty


def test_load_usage_data_casts_numeric_strings(tmp_path, monkeypatch):
    master_file = tmp_path / "all_usage_runs.json"
    master_file.write_text(
        json.dumps(
            [
                {
                    "timestamp": "2026-07-06T12:00:00",
                    "output_file": "generated-vplan.json",
                    "summary": {
                        "prompt_tokens": "10",
                        "completion_tokens": "20",
                        "total_tokens": "30",
                        "total_cost": "0.001",
                        "agents": [
                            {
                                "agent_name": "vplan_generator",
                                "model_name": "gpt-5.4",
                                "prompt_tokens": "5",
                                "completion_tokens": "10",
                                "total_tokens": "15",
                                "total_cost": "0.0005",
                            }
                        ],
                    },
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(analysis, "MASTER_USAGE_FILE", master_file)

    run_df, agent_df = analysis.load_usage_data()

    assert run_df.iloc[0]["prompt_tokens"] == 10
    assert run_df.iloc[0]["completion_tokens"] == 20
    assert run_df.iloc[0]["total_tokens"] == 30
    assert run_df.iloc[0]["total_cost"] == 0.001

    assert agent_df.iloc[0]["prompt_tokens"] == 5
    assert agent_df.iloc[0]["completion_tokens"] == 10
    assert agent_df.iloc[0]["total_tokens"] == 15
    assert agent_df.iloc[0]["total_cost"] == 0.0005


def test_load_usage_data_raises_for_malformed_json(tmp_path, monkeypatch):
    master_file = tmp_path / "all_usage_runs.json"
    master_file.write_text("{ bad json", encoding="utf-8")

    monkeypatch.setattr(analysis, "MASTER_USAGE_FILE", master_file)

    with pytest.raises(json.JSONDecodeError):
        analysis.load_usage_data()


# ---------------------------------------------------------------------------
# save_csvs
# ---------------------------------------------------------------------------


def test_save_csvs_writes_run_and_agent_csvs(patched_usage_paths):
    run_df, agent_df = analysis.load_usage_data()

    analysis.save_csvs(run_df, agent_df)

    run_csv = patched_usage_paths / "usage_by_run.csv"
    agent_csv = patched_usage_paths / "usage_by_agent.csv"

    assert run_csv.exists()
    assert agent_csv.exists()

    saved_run_df = pd.read_csv(run_csv)
    saved_agent_df = pd.read_csv(agent_csv)

    assert len(saved_run_df) == 2
    assert len(saved_agent_df) == 3


# ---------------------------------------------------------------------------
# plotting functions
# ---------------------------------------------------------------------------


def test_plot_total_cost_by_run_creates_png(patched_usage_paths):
    run_df, agent_df = analysis.load_usage_data()

    analysis.plot_total_cost_by_run(run_df)

    output_file = patched_usage_paths / "estimated_cost_by_run.png"

    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_plot_total_tokens_by_run_creates_png(patched_usage_paths):
    run_df, agent_df = analysis.load_usage_data()

    analysis.plot_total_tokens_by_run(run_df)

    output_file = patched_usage_paths / "total_tokens_by_run.png"

    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_plot_cost_by_agent_creates_png(patched_usage_paths):
    run_df, agent_df = analysis.load_usage_data()

    analysis.plot_cost_by_agent(agent_df)

    output_file = patched_usage_paths / "estimated_cost_by_agent.png"

    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_plot_tokens_by_agent_creates_png(patched_usage_paths):
    run_df, agent_df = analysis.load_usage_data()

    analysis.plot_tokens_by_agent(agent_df)

    output_file = patched_usage_paths / "tokens_by_agent.png"

    assert output_file.exists()
    assert output_file.stat().st_size > 0


# ---------------------------------------------------------------------------
# generate_usage_reports
# ---------------------------------------------------------------------------


def test_generate_usage_reports_returns_empty_dict_when_no_usage_data(
    tmp_path,
    monkeypatch,
):
    missing_file = tmp_path / "missing-all-usage-runs.json"
    charts_dir = tmp_path / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(analysis, "MASTER_USAGE_FILE", missing_file)
    monkeypatch.setattr(analysis, "CHARTS_DIR", charts_dir)

    result = analysis.generate_usage_reports()

    assert result == {}


def test_generate_usage_reports_creates_csvs_and_charts(patched_usage_paths):
    result = analysis.generate_usage_reports()

    assert result == {
        "usage_by_run_csv": "usage_by_run.csv",
        "usage_by_agent_csv": "usage_by_agent.csv",
        "estimated_cost_by_run": "estimated_cost_by_run.png",
        "total_tokens_by_run": "total_tokens_by_run.png",
        "estimated_cost_by_agent": "estimated_cost_by_agent.png",
        "tokens_by_agent": "tokens_by_agent.png",
    }

    expected_files = [
        "usage_by_run.csv",
        "usage_by_agent.csv",
        "estimated_cost_by_run.png",
        "total_tokens_by_run.png",
        "estimated_cost_by_agent.png",
        "tokens_by_agent.png",
    ]

    for filename in expected_files:
        output_file = patched_usage_paths / filename
        assert output_file.exists()
        assert output_file.stat().st_size > 0


def test_generate_usage_reports_skips_agent_charts_when_agent_df_empty(
    tmp_path,
    monkeypatch,
):
    master_file = tmp_path / "all_usage_runs.json"
    charts_dir = tmp_path / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    master_file.write_text(
        json.dumps(
            [
                {
                    "timestamp": "2026-07-06T12:00:00",
                    "output_file": "generated-vplan.json",
                    "summary": {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                        "total_cost": "0.001",
                        "agents": [],
                    },
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(analysis, "MASTER_USAGE_FILE", master_file)
    monkeypatch.setattr(analysis, "CHARTS_DIR", charts_dir)

    result = analysis.generate_usage_reports()

    assert result == {
        "usage_by_run_csv": "usage_by_run.csv",
        "usage_by_agent_csv": "usage_by_agent.csv",
        "estimated_cost_by_run": "estimated_cost_by_run.png",
        "total_tokens_by_run": "total_tokens_by_run.png",
    }

    assert (charts_dir / "usage_by_run.csv").exists()
    assert (charts_dir / "usage_by_agent.csv").exists()
    assert (charts_dir / "estimated_cost_by_run.png").exists()
    assert (charts_dir / "total_tokens_by_run.png").exists()

    assert not (charts_dir / "estimated_cost_by_agent.png").exists()
    assert not (charts_dir / "tokens_by_agent.png").exists()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_prints_generated_reports(
    patched_usage_paths,
    capsys,
):
    analysis.main()

    captured = capsys.readouterr()

    assert "Generated usage reports:" in captured.out
    assert "Saved usage CSVs and charts to:" in captured.out
    assert str(patched_usage_paths) in captured.out
