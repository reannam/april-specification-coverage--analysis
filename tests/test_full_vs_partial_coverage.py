import pytest

from Backend.coverage import full_vs_partial_coverage as metric


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("Covered", 1.0),
        ("fully_covered", 1.0),
        ("Partially covered", 0.5),
        ("partially_covered", 0.5),
        ("Uncovered", 0.0),
        (None, 0.0),
        ("unexpected", 0.0),
    ],
)
def test_status_to_weight(status, expected):
    assert metric.status_to_weight(status) == expected


def test_extract_labelled_requirements_validation():
    assert metric.extract_labelled_requirements({"labelled_requirements": []}) == []

    with pytest.raises(ValueError):
        metric.extract_labelled_requirements({"labelled_requirements": "bad"})


def test_calculate_full_vs_partial_coverage(sample_labelled_requirements):
    result = metric.calculate_full_vs_partial_coverage(sample_labelled_requirements)

    assert result["total_requirements"] == 3
    assert result["fully_covered_count"] == 1
    assert result["partially_covered_count"] == 1
    assert result["not_covered_count"] == 1
    assert result["weighted_score"] == 1.5
    assert result["weighted_coverage"] == 50.0
    assert result["fully_covered_requirements"][0]["requirement_id"] == "REQ_A2_1_001"


def test_calculate_empty_input_returns_zero():
    result = metric.calculate_full_vs_partial_coverage([])

    assert result["weighted_score"] == 0
    assert result["weighted_coverage"] == 0.0


def test_run_full_vs_partial_coverage(
    tmp_path, write_json, sample_labelled_requirements
):
    path = write_json(
        tmp_path / "coverage.json",
        {"labelled_requirements": sample_labelled_requirements},
    )

    result = metric.run_full_vs_partial_coverage(path)

    assert result["weighted_coverage"] == 50.0


def test_print_summary_lists_uncovered(capsys):
    metric.print_full_vs_partial_summary(
        {
            "total_requirements": 1,
            "fully_covered_count": 0,
            "partially_covered_count": 0,
            "not_covered_count": 1,
            "weighted_score": 0,
            "weighted_coverage": 0.0,
            "not_covered_requirements": [{"requirement_id": "REQ_1"}],
        }
    )

    output = capsys.readouterr().out
    assert "Full vs Partial Coverage" in output
    assert "REQ_1" in output
