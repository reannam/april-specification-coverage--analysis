import argparse
import json
from pathlib import Path

from Backend.AnalyseAndCompareSpecs.comparator import run_comparison
from Backend.AnalyseAndCompareSpecs.quality_check import build_report


def extracted_document(*, name: str, requirement_text: str) -> dict:
    """Return the smallest valid extractor-shaped document used by these tests."""

    return {
        "document_name": name,
        "metadata": {},
        "total_pages": 0,
        "sections": [],
        "requirements": [{"id": "REQ_001", "text": requirement_text}],
        "figures": [],
        "tables": [],
        "notes": [],
        "acronyms": [],
        "cross_references": [],
        "semantic_chunks": [],
        "pages": [],
    }


def test_comparison_writes_all_report_formats(tmp_path):
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(
        json.dumps(
            extracted_document(name="old", requirement_text="Unit shall reset.")
        ),
        encoding="utf-8",
    )
    new_path.write_text(
        json.dumps(
            extracted_document(
                name="new",
                requirement_text="Unit shall reset within two cycles.",
            )
        ),
        encoding="utf-8",
    )

    result = run_comparison(old_path, new_path, tmp_path, filename_prefix="test")

    assert result["report"]["summary"]["total_changes"] > 0
    assert set(result["output_files"]) == {"csv", "json", "markdown"}
    assert all(Path(path).is_file() for path in result["output_files"].values())


def test_quality_report_exposes_formula_components(tmp_path):
    document_path = tmp_path / "document.json"
    document_path.write_text(
        json.dumps(
            extracted_document(
                name="example",
                requirement_text="Unit shall reset.",
            )
        ),
        encoding="utf-8",
    )

    report = build_report(
        argparse.Namespace(
            json=str(document_path),
            pdf=None,
            gold_json=None,
            threshold=95.0,
            report_json=None,
        )
    )

    assert set(report["scores"]) == {
        "completeness",
        "accuracy",
        "table_figure_capture",
    }
    assert all(score["formula"] for score in report["scores"].values())
    assert report["overall_status"] in {"pass", "fail"}
