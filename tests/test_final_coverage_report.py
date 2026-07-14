import json
from pathlib import Path

import pytest

from Backend.coverage import final_coverage_report as report_module


def test_normalise_status():
    assert report_module.normalise_status("covered") == "Covered"
    assert report_module.normalise_status("partially_covered") == "Partially covered"
    assert (
        report_module.normalise_status("ambiguous") == "Ambiguous / not yet plannable"
    )
    assert report_module.normalise_status("unknown") == "Uncovered"


def test_determine_requirement_weight_rules(monkeypatch):
    monkeypatch.setattr(
        report_module,
        "TERM_GROUPS",
        {
            "critical_terms": ["shall", "must"],
            "optional_terms": ["may"],
            "explanatory_terms": ["for example"],
            "important_functional_terms": ["transfer"],
        },
    )

    assert (
        report_module.determine_requirement_weight(
            {"text": "For example, a transfer can occur."}
        )[0]
        == 1
    )
    assert (
        report_module.determine_requirement_weight(
            {"text": "The device may transfer."}
        )[0]
        == 1
    )
    assert (
        report_module.determine_requirement_weight(
            {"text": "The device shall transfer."}
        )[0]
        == 3
    )
    assert (
        report_module.determine_requirement_weight(
            {"text": "Transfer data", "type": "protocol_rule"}
        )[0]
        == 2
    )
    assert (
        report_module.determine_requirement_weight(
            {"text": "Other rule", "source_section": "A2.1"}
        )[0]
        == 2
    )


def test_supporting_calculations(
    sample_spec, sample_vplan, sample_labelled_requirements
):
    mapping = report_module.calculate_requirement_mapping_coverage(
        sample_spec["requirements"], sample_vplan["feature_list"]
    )
    weighted = report_module.calculate_weighted_coverage(sample_labelled_requirements)
    traceability = report_module.calculate_traceability_coverage(
        sample_vplan["feature_list"]
    )
    orphan = report_module.calculate_orphan_rate(
        sample_spec["requirements"],
        sample_vplan["feature_list"]
        + [{"test_id": "ORPHAN", "requirement_id": "REQ_MISSING"}],
    )
    testability = report_module.calculate_testability_from_coverage_status(
        sample_labelled_requirements
    )

    assert mapping["requirement_mapping_coverage"] == 66.67
    assert weighted["weighted_coverage"] == 50.0
    assert traceability["traceability_coverage"] == 100.0
    assert orphan["orphan_rate"] == 33.33
    assert testability["testability_coverage"] == 66.67


def test_build_coverage_summary(sample_spec, sample_labelled_requirements):
    result = report_module.build_coverage_summary(
        sample_spec["requirements"],
        sample_labelled_requirements,
        {"orphan_vplan_items": 2},
    )

    assert result == {
        "total_spec_items": 3,
        "covered": 1,
        "partially_covered": 1,
        "uncovered": 0,
        "ambiguity_blocked": 1,
        "orphan_vplan_items": 2,
    }


def test_gap_report_excludes_covered_and_sorts_by_rank(
    monkeypatch, sample_labelled_requirements
):
    monkeypatch.setattr(
        report_module,
        "TERM_GROUPS",
        {
            "critical_terms": ["shall"],
            "optional_terms": ["may"],
            "explanatory_terms": ["for example"],
            "important_functional_terms": ["transfer"],
        },
    )

    gaps = report_module.build_gap_report(sample_labelled_requirements)

    assert len(gaps) == 2
    assert gaps[0]["requirement_id"] == "REQ_A2_1_003"
    assert all(row["coverage_status"] != "Covered" for row in gaps)


def test_ambiguity_report_includes_status_or_evidence(sample_labelled_requirements):
    rows = report_module.build_ambiguity_report(sample_labelled_requirements)

    assert {row["requirement_id"] for row in rows} == {
        "REQ_A2_1_002",
        "REQ_A2_1_003",
    }


def test_build_final_coverage_report_from_files(
    tmp_path,
    write_json,
    sample_spec,
    sample_vplan,
    sample_labelled_requirements,
    monkeypatch,
):
    monkeypatch.setattr(
        report_module,
        "TERM_GROUPS",
        {
            "critical_terms": ["shall"],
            "optional_terms": ["may"],
            "explanatory_terms": ["for example"],
            "important_functional_terms": ["transfer"],
        },
    )
    spec = write_json(tmp_path / "spec.json", sample_spec)
    vplan = write_json(tmp_path / "vplan.json", sample_vplan)
    coverage = write_json(
        tmp_path / "coverage.json",
        {"labelled_requirements": sample_labelled_requirements},
    )

    report = report_module.build_final_coverage_report(spec, vplan, coverage)

    assert report["coverage_summary"]["total_spec_items"] == 3
    assert report["coverage_percentages"]["weighted_coverage"] == 50.0
    assert "supporting_metrics" in report


def test_write_final_outputs_creates_four_files(tmp_path):
    report = {
        "metadata": {},
        "coverage_summary": {},
        "coverage_percentages": {},
        "gap_report": [],
        "ambiguity_report": [],
    }

    outputs = report_module.write_final_outputs(report, tmp_path)

    assert set(outputs) == {
        "coverage_summary_file",
        "gap_report_file",
        "ambiguity_report_file",
        "final_coverage_report_file",
    }
    assert all(Path(path).exists() for path in outputs.values())


def test_run_final_coverage_report_returns_report_and_files(tmp_path, monkeypatch):
    fake_report = {
        "metadata": {},
        "coverage_summary": {},
        "coverage_percentages": {},
        "gap_report": [],
        "ambiguity_report": [],
    }
    monkeypatch.setattr(
        report_module,
        "build_final_coverage_report",
        lambda **kwargs: fake_report,
    )
    monkeypatch.setattr(
        report_module,
        "print_final_report_summary",
        lambda report, output_files: None,
    )

    result = report_module.run_final_coverage_report(
        "spec.json", "vplan.json", "coverage.json", tmp_path
    )

    assert result["report"] is fake_report
    assert Path(result["output_files"]["final_coverage_report_file"]).exists()
