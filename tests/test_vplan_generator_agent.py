from Backend.agents import vplan_generator_utils as utils

# ---------------------------------------------------------------------------
# chunk_requirements
# ---------------------------------------------------------------------------


def test_chunk_requirements_splits_into_batches():
    requirements = [
        {"id": "REQ_001"},
        {"id": "REQ_002"},
        {"id": "REQ_003"},
        {"id": "REQ_004"},
        {"id": "REQ_005"},
    ]

    result = utils.chunk_requirements(requirements, batch_size=2)

    assert result == [
        [{"id": "REQ_001"}, {"id": "REQ_002"}],
        [{"id": "REQ_003"}, {"id": "REQ_004"}],
        [{"id": "REQ_005"}],
    ]


def test_chunk_requirements_returns_single_batch_when_smaller_than_batch_size():
    requirements = [
        {"id": "REQ_001"},
        {"id": "REQ_002"},
    ]

    result = utils.chunk_requirements(requirements, batch_size=30)

    assert result == [
        [{"id": "REQ_001"}, {"id": "REQ_002"}],
    ]


def test_chunk_requirements_returns_empty_list_for_empty_requirements():
    result = utils.chunk_requirements([], batch_size=30)

    assert result == []


# ---------------------------------------------------------------------------
# filter_edge_cases_for_batch
# ---------------------------------------------------------------------------


def test_filter_edge_cases_for_batch_keeps_only_matching_requirement_ids():
    edge_cases = {
        "edge_cases": [
            {
                "edge_case_id": "EDGE_001",
                "requirement_id": "REQ_001",
            },
            {
                "edge_case_id": "EDGE_002",
                "requirement_id": "REQ_002",
            },
            {
                "edge_case_id": "EDGE_003",
                "requirement_id": "REQ_999",
            },
        ]
    }

    requirements_batch = [
        {"id": "REQ_001"},
        {"id": "REQ_002"},
    ]

    result = utils.filter_edge_cases_for_batch(edge_cases, requirements_batch)

    assert result == {
        "edge_cases": [
            {
                "edge_case_id": "EDGE_001",
                "requirement_id": "REQ_001",
            },
            {
                "edge_case_id": "EDGE_002",
                "requirement_id": "REQ_002",
            },
        ]
    }


def test_filter_edge_cases_for_batch_returns_empty_when_no_edge_cases():
    requirements_batch = [
        {"id": "REQ_001"},
    ]

    result = utils.filter_edge_cases_for_batch(None, requirements_batch)

    assert result == {"edge_cases": []}


def test_filter_edge_cases_for_batch_ignores_requirements_without_ids():
    edge_cases = {
        "edge_cases": [
            {
                "edge_case_id": "EDGE_001",
                "requirement_id": "REQ_001",
            }
        ]
    }

    requirements_batch = [
        {"description": "Missing ID"},
        "bad row",
    ]

    result = utils.filter_edge_cases_for_batch(edge_cases, requirements_batch)

    assert result == {"edge_cases": []}


# ---------------------------------------------------------------------------
# ensure_unique_test_ids
# ---------------------------------------------------------------------------


def test_ensure_unique_test_ids_leaves_unique_ids_unchanged():
    rows = [
        {"test_id": "TEST_001"},
        {"test_id": "TEST_002"},
    ]

    result = utils.ensure_unique_test_ids(rows)

    assert result == [
        {"test_id": "TEST_001"},
        {"test_id": "TEST_002"},
    ]


def test_ensure_unique_test_ids_renames_duplicates():
    rows = [
        {"test_id": "TEST_001"},
        {"test_id": "TEST_001"},
        {"test_id": "TEST_001"},
    ]

    result = utils.ensure_unique_test_ids(rows)

    assert result == [
        {"test_id": "TEST_001"},
        {"test_id": "TEST_001_DUP2"},
        {"test_id": "TEST_001_DUP3"},
    ]


def test_ensure_unique_test_ids_uses_test_unknown_when_missing():
    rows = [
        {},
        {},
    ]

    result = utils.ensure_unique_test_ids(rows)

    assert result == [
        {"test_id": "TEST_UNKNOWN"},
        {"test_id": "TEST_UNKNOWN_DUP2"},
    ]


def test_ensure_unique_test_ids_mutates_and_returns_same_list():
    rows = [
        {"test_id": "TEST_001"},
        {"test_id": "TEST_001"},
    ]

    result = utils.ensure_unique_test_ids(rows)

    assert result is rows


# ---------------------------------------------------------------------------
# to_int
# ---------------------------------------------------------------------------


def test_to_int_converts_valid_values():
    assert utils.to_int(10) == 10
    assert utils.to_int("10") == 10
    assert utils.to_int(10.5) == 10


def test_to_int_returns_zero_for_invalid_values():
    assert utils.to_int(None) == 0
    assert utils.to_int("bad") == 0
    assert utils.to_int({}) == 0


# ---------------------------------------------------------------------------
# to_float
# ---------------------------------------------------------------------------


def test_to_float_converts_valid_values():
    assert utils.to_float(10) == 10.0
    assert utils.to_float("10.5") == 10.5
    assert utils.to_float("$1,234.56") == 1234.56


def test_to_float_returns_zero_for_invalid_values():
    assert utils.to_float(None) == 0.0
    assert utils.to_float("bad") == 0.0
    assert utils.to_float({}) == 0.0


# ---------------------------------------------------------------------------
# combine_usage
# ---------------------------------------------------------------------------


def test_combine_usage_combines_batch_usage_records():
    batch_usages = [
        {
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "total_tokens": 300,
            "total_cost": "0.01",
        },
        {
            "prompt_tokens": 50,
            "completion_tokens": 75,
            "total_tokens": 125,
            "total_cost": "0.02",
        },
    ]

    result = utils.combine_usage(batch_usages)

    assert result["agent_name"] == "vplan_generator"
    assert result["model_name"] == "gpt-5.4"
    assert result["prompt_tokens"] == 150
    assert result["completion_tokens"] == 275
    assert result["total_tokens"] == 425
    assert result["number_of_batches"] == 2
    assert result["batches"] == batch_usages


def test_combine_usage_handles_empty_batch_usage_list():
    result = utils.combine_usage([])

    assert result["agent_name"] == "vplan_generator"
    assert result["prompt_tokens"] == 0
    assert result["completion_tokens"] == 0
    assert result["total_tokens"] == 0
    assert result["number_of_batches"] == 0
    assert result["batches"] == []


def test_combine_usage_handles_bad_values():
    batch_usages = [
        {
            "prompt_tokens": "bad",
            "completion_tokens": None,
            "total_tokens": {},
            "total_cost": "$1,000.50",
        }
    ]

    result = utils.combine_usage(batch_usages)

    assert result["prompt_tokens"] == 0
    assert result["completion_tokens"] == 0
    assert result["total_tokens"] == 0
    assert result["number_of_batches"] == 1
