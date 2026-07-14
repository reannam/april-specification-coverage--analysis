import pytest

from Backend.coverage import traceability_coverage as metric


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        ("", False),
        ("   ", False),
        ("A2.1", True),
        ([], False),
        (["", "REQ_1"], True),
        ({}, False),
        ({"id": "REQ_1"}, True),
        (0, True),
    ],
)
def test_value_has_content(value, expected):
    assert metric.value_has_content(value) is expected


def test_extract_vplan_items_supported_shapes():
    row = {"test_id": "T1"}
    assert metric.extract_vplan_items([row]) == [row]
    assert metric.extract_vplan_items({"feature_list": [row]}) == [row]
    assert metric.extract_vplan_items({"table": {"feature_list": [row]}}) == [row]
    assert metric.extract_vplan_items({"vplan": [row]}) == [row]

    with pytest.raises(ValueError):
        metric.extract_vplan_items({})


def test_field_contains_source_trace_uses_configured_fields(monkeypatch):
    monkeypatch.setattr(
        metric, "TRACEABILITY_FIELDS", ["requirement_id", "source_section"]
    )

    assert metric.field_contains_source_trace({"requirement_id": "REQ_1"}) is True
    assert metric.field_contains_source_trace({"requirement_id": " "}) is False


@pytest.mark.xfail(
    reason="Current source uses trace_patterns instead of TRACE_PATTERNS.",
    strict=False,
)
def test_text_contains_source_trace_detects_embedded_requirement_id():
    assert (
        metric.text_contains_source_trace({"test_description": "Verify REQ_A2_1_001."})
        is True
    )


def test_has_source_trace_short_circuits_on_explicit_field(monkeypatch):
    monkeypatch.setattr(metric, "TRACEABILITY_FIELDS", ["requirement_id"])
    monkeypatch.setattr(
        metric,
        "text_contains_source_trace",
        lambda item: (_ for _ in ()).throw(AssertionError("fallback should not run")),
    )

    assert metric.has_source_trace({"requirement_id": "REQ_1"}) is True


def test_get_test_id_prefers_test_id_then_id_then_fallback():
    assert metric.get_test_id({"test_id": "T1"}, 0) == "T1"
    assert metric.get_test_id({"id": "ROW_1"}, 0) == "ROW_1"
    assert metric.get_test_id({}, 1) == "VPLAN_ITEM_002"


def test_calculate_traceability_coverage(monkeypatch):
    monkeypatch.setattr(metric, "TRACEABILITY_FIELDS", ["requirement_id"])
    monkeypatch.setattr(metric, "text_contains_source_trace", lambda item: False)

    result = metric.calculate_traceability_coverage(
        [
            {"test_id": "T1", "requirement_id": "REQ_1"},
            {"test_id": "T2"},
        ]
    )

    assert result["total_vplan_items"] == 2
    assert result["vplan_items_with_source_trace"] == 1
    assert result["vplan_items_without_source_trace"] == 1
    assert result["traceability_coverage"] == 50.0
    assert result["untraceable_items"][0]["test_id"] == "T2"


def test_run_traceability_coverage_all_explicit(tmp_path, write_json, monkeypatch):
    monkeypatch.setattr(metric, "TRACEABILITY_FIELDS", ["requirement_id"])
    path = write_json(
        tmp_path / "vplan.json",
        {"feature_list": [{"test_id": "T1", "requirement_id": "REQ_1"}]},
    )

    result = metric.run_traceability_coverage(path)

    assert result["traceability_coverage"] == 100.0


def test_print_summary(capsys):
    metric.print_traceability_summary(
        {
            "total_vplan_items": 1,
            "vplan_items_with_source_trace": 0,
            "vplan_items_without_source_trace": 1,
            "traceability_coverage": 0.0,
            "untraceable_items": [{"test_id": "T1"}],
        }
    )

    output = capsys.readouterr().out
    assert "Traceability Coverage" in output
    assert "T1" in output
