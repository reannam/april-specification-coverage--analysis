import csv
import json
from pathlib import Path

import pytest

from Backend.coverage import overall_coverage as metric


@pytest.fixture
def configured_metric(monkeypatch):
    monkeypatch.setattr(metric, "COVERED_STATUSES", {"covered", "fully covered"})
    monkeypatch.setattr(metric, "PARTIALLY_COVERED_STATUSES", {"partially covered"})
    monkeypatch.setattr(metric, "AMBIGUOUS_STATUSES", {"ambiguous"})
    monkeypatch.setattr(metric, "NOT_COVERED_STATUSES", {"uncovered", "not covered"})
    monkeypatch.setattr(
        metric,
        "COVERAGE_WEIGHTS",
        {
            "Covered": 1.0,
            "Partially covered": 0.5,
            "Ambiguous / not yet plannable": 0.0,
            "Uncovered": 0.0,
        },
        raising=False,
    )
    monkeypatch.setattr(metric, "critical_terms", {"shall", "must"}, raising=False)
    monkeypatch.setattr(metric, "optional_terms", {"may"}, raising=False)
    monkeypatch.setattr(metric, "explanatory_terms", {"for example"}, raising=False)
    monkeypatch.setattr(
        metric, "important_functional_terms", {"transfer"}, raising=False
    )


def test_load_term_groups(tmp_path):
    path = tmp_path / "terms.txt"
    path.write_text("[group]\nOne\nTWO\n", encoding="utf-8")

    assert metric.load_term_groups(path) == {"group": {"one", "two"}}


def test_extract_labelled_requirements_validation():
    assert metric.extract_labelled_requirements({"labelled_requirements": []}) == []
    with pytest.raises(ValueError):
        metric.extract_labelled_requirements({"labelled_requirements": {}})


def test_normalise_status_and_score(configured_metric):
    assert metric.normalise_coverage_status(" COVERED ") == "Covered"
    assert metric.normalise_coverage_status("partially covered") == "Partially covered"
    assert (
        metric.normalise_coverage_status("ambiguous") == "Ambiguous / not yet plannable"
    )
    assert metric.normalise_coverage_status("unknown") == "Uncovered"
    assert metric.coverage_status_to_score("covered") == 1.0
    assert metric.coverage_status_to_score("partially covered") == 0.5


def test_determine_requirement_weight(configured_metric):
    assert (
        metric.determine_requirement_weight({"text": "For example, transfer data."})[0]
        == 1
    )
    assert (
        metric.determine_requirement_weight({"text": "The device may transfer."})[0]
        == 1
    )
    assert (
        metric.determine_requirement_weight({"text": "The device shall transfer."})[0]
        == 3
    )
    assert (
        metric.determine_requirement_weight(
            {"text": "Transfer data", "type": "protocol_rule"}
        )[0]
        == 2
    )
    assert (
        metric.determine_requirement_weight(
            {"text": "Other", "source_section": "A2.1"}
        )[0]
        == 2
    )


def test_build_rows_and_calculate_score(configured_metric):
    rows = metric.build_overall_coverage_rows(
        [
            {
                "id": "REQ_1",
                "text": "The device shall transfer.",
                "verified_coverage_status": "covered",
                "linked_tests": ["T1"],
            },
            {
                "id": "REQ_2",
                "text": "The device may transfer.",
                "verified_coverage_status": "partially covered",
                "linked_tests": ["T2"],
            },
        ]
    )
    summary = metric.calculate_overall_coverage_score(rows)

    assert rows[0]["importance_weight"] == 3
    assert rows[0]["weighted_score"] == 3.0
    assert rows[1]["weighted_score"] == 0.5
    assert summary["total_weight"] == 4
    assert summary["overall_coverage_score"] == 87.5


def test_calculate_score_empty_rows():
    result = metric.calculate_overall_coverage_score([])
    assert result["overall_coverage_score"] == 0.0


def test_build_report_and_save_files(tmp_path, write_json, configured_metric):
    coverage_file = write_json(
        tmp_path / "coverage.json",
        {
            "labelled_requirements": [
                {
                    "id": "REQ_1",
                    "text": "The device shall transfer.",
                    "verified_coverage_status": "covered",
                    "linked_tests": ["T1"],
                }
            ]
        },
    )

    report = metric.build_overall_coverage_report(coverage_file)
    json_path = metric.save_json_report(report, tmp_path / "out" / "report.json")
    csv_path = metric.save_csv_table(report, tmp_path / "out" / "report.csv")

    assert (
        json.loads(json_path.read_text(encoding="utf-8"))["overall_coverage_summary"][
            "overall_coverage_score"
        ]
        == 100.0
    )
    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["requirement_id"] == "REQ_1"
    assert rows[0]["overall_coverage_score"] == "100.0"


def test_run_overall_coverage_returns_output_paths(
    tmp_path, write_json, configured_metric
):
    coverage_file = write_json(
        tmp_path / "coverage.json",
        {"labelled_requirements": []},
    )

    result = metric.run_overall_coverage(
        coverage_file,
        tmp_path / "report.json",
        tmp_path / "report.csv",
    )

    assert result["overall_coverage_score"] == 0.0
    assert Path(result["json_output_file"]).exists()
    assert Path(result["csv_output_file"]).exists()


def test_print_summary(capsys):
    metric.print_overall_coverage_summary(
        {
            "total_items": 1,
            "total_weight": 3,
            "total_weighted_score": 3,
            "overall_coverage_score": 100.0,
            "json_output_file": "report.json",
            "csv_output_file": None,
        }
    )
    assert "Overall Spec-to-vPlan Coverage" in capsys.readouterr().out
