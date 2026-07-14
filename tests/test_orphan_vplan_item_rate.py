import pytest

from Backend.coverage import orphan_vplan_item_rate as metric


def test_load_text_config(tmp_path):
    path = tmp_path / "terms.txt"
    path.write_text(
        """
# comment
[traceability_fields]
requirement_id
source_section
[regex_patterns]
section=A\\d+\\.\\d+
requirement=REQ_[A-Z0-9_]+
table=Table\\s+[A-Z0-9.]+
figure=Figure\\s+[A-Z0-9.]+
""".strip(),
        encoding="utf-8",
    )

    groups, regex = metric.load_text_config(path)

    assert groups["traceability_fields"] == ["requirement_id", "source_section"]
    assert regex["requirement"] == "REQ_[A-Z0-9_]+"


def test_load_text_config_rejects_value_before_heading(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text("requirement_id", encoding="utf-8")

    with pytest.raises(ValueError):
        metric.load_text_config(path)


def test_extract_spec_sources(sample_spec):
    sources = metric.extract_spec_sources(sample_spec)

    assert "REQ_A2_1_001" in sources["requirement_ids"]
    assert sources["section_ids"] == {"A2.1"}
    assert sources["page_numbers"] == {"12"}


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, False), (" ", False), (["", "x"], True), ({"a": ""}, False), (1, True)],
)
def test_value_has_content(value, expected):
    assert metric.value_has_content(value) is expected


def test_collect_explicit_trace_values(monkeypatch):
    monkeypatch.setattr(
        metric, "TRACEABILITY_FIELDS", ["requirement_id", "source_refs"]
    )

    values = metric.collect_explicit_trace_values(
        {"requirement_id": "REQ_1", "source_refs": ["A1", ""]}
    )

    assert values == ["REQ_1", "A1"]


def test_normalise_table_or_figure_reference():
    assert metric.normalise_table_or_figure_reference(" Table A2.1 ") == "A2.1"
    assert metric.normalise_table_or_figure_reference("Figure A2.2") == "A2.2"


def test_trace_value_exists_in_spec(sample_spec):
    sources = metric.extract_spec_sources(sample_spec)

    assert metric.trace_value_exists_in_spec("REQ_A2_1_001", sources) is True
    assert metric.trace_value_exists_in_spec("Table A2.1", sources) is True
    assert metric.trace_value_exists_in_spec("REQ_MISSING", sources) is False


def test_calculate_orphan_vplan_item_rate(sample_spec, monkeypatch):
    monkeypatch.setattr(
        metric, "TRACEABILITY_FIELDS", ["requirement_id", "source_section"]
    )

    result = metric.calculate_orphan_vplan_item_rate(
        sample_spec,
        [
            {"test_id": "T1", "requirement_id": "REQ_A2_1_001"},
            {"test_id": "T2", "requirement_id": "REQ_MISSING"},
        ],
    )

    assert result["total_vplan_items"] == 2
    assert result["vplan_items_with_source_in_spec"] == 1
    assert result["orphan_vplan_items"] == 1
    assert result["orphan_rate"] == 50.0
    assert result["orphan_items"][0]["test_id"] == "T2"


def test_run_orphan_vplan_item_rate(tmp_path, write_json, sample_spec, monkeypatch):
    monkeypatch.setattr(metric, "TRACEABILITY_FIELDS", ["requirement_id"])
    spec = write_json(tmp_path / "spec.json", sample_spec)
    vplan = write_json(
        tmp_path / "vplan.json",
        {"feature_list": [{"test_id": "T1", "requirement_id": "REQ_A2_1_001"}]},
    )

    result = metric.run_orphan_vplan_item_rate(spec, vplan)

    assert result["orphan_rate"] == 0.0


def test_run_rejects_non_object_spec(tmp_path, write_json):
    spec = write_json(tmp_path / "spec.json", [])
    vplan = write_json(tmp_path / "vplan.json", {"feature_list": []})

    with pytest.raises(ValueError, match="JSON object"):
        metric.run_orphan_vplan_item_rate(spec, vplan)


def test_print_summary(capsys):
    metric.print_orphan_vplan_item_rate_summary(
        {
            "total_vplan_items": 1,
            "vplan_items_with_source_in_spec": 0,
            "orphan_vplan_items": 1,
            "orphan_rate": 100.0,
            "orphan_items": [{"test_id": "T1"}],
        }
    )
    output = capsys.readouterr().out
    assert "Orphan vPlan Item Rate" in output
    assert "T1" in output
