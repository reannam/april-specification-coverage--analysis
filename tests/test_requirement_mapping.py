import pytest

from Backend.coverage import requirement_mapping as metric


@pytest.mark.parametrize(
    "payload",
    [
        [{"test_id": "T1"}],
        {"feature_list": [{"test_id": "T1"}]},
        {"table": {"feature_list": [{"test_id": "T1"}]}},
        {"vplan": [{"test_id": "T1"}]},
    ],
)
def test_extract_vplan_items_supported_shapes(payload):
    assert metric.extract_vplan_items(payload) == [{"test_id": "T1"}]


def test_extract_vplan_items_rejects_unknown_shape():
    with pytest.raises(ValueError):
        metric.extract_vplan_items({"tests": []})


def test_extract_spec_requirements_validation():
    assert metric.extract_spec_requirements({"requirements": []}) == []

    with pytest.raises(ValueError):
        metric.extract_spec_requirements({"requirements": {}})


@pytest.mark.parametrize(
    ("item", "expected"),
    [({"requirement_id": "REQ_1"}, "REQ_1"), ({"id": 2}, "2"), ({}, None)],
)
def test_get_requirement_id(item, expected):
    assert metric.get_requirement_id(item) == expected


def test_calculate_requirement_mapping_coverage(sample_spec, sample_vplan):
    result = metric.calculate_requirement_mapping_coverage(
        sample_spec["requirements"], sample_vplan["feature_list"]
    )

    assert result["total_spec_items"] == 3
    assert result["spec_items_mapped_to_vplan"] == 2
    assert result["spec_items_unmapped_to_vplan"] == 1
    assert result["requirement_mapping_coverage"] == 66.67
    assert result["unmapped_requirement_ids"] == ["REQ_A2_1_003"]


def test_empty_spec_returns_zero_coverage():
    result = metric.calculate_requirement_mapping_coverage([], [])
    assert result["requirement_mapping_coverage"] == 0.0


def test_run_requirement_mapping_coverage(
    tmp_path, write_json, sample_spec, sample_vplan
):
    spec_file = write_json(tmp_path / "spec.json", sample_spec)
    vplan_file = write_json(tmp_path / "vplan.json", sample_vplan)

    result = metric.run_requirement_mapping_coverage(spec_file, vplan_file)

    assert result["spec_items_mapped_to_vplan"] == 2


def test_print_summary(capsys):
    metric.print_requirement_mapping_summary(
        {
            "total_spec_items": 2,
            "spec_items_mapped_to_vplan": 1,
            "spec_items_unmapped_to_vplan": 1,
            "requirement_mapping_coverage": 50.0,
            "unmapped_requirement_ids": ["REQ_2"],
        }
    )

    output = capsys.readouterr().out
    assert "Requirement Mapping Coverage" in output
    assert "REQ_2" in output
