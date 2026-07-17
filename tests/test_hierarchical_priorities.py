import json

import pytest

from Backend.config import MAX_PRIORITY_SELECTIONS
from Backend.vPlan.post_processing.prioritise_vplan import prioritise_vplan


def _write_vplan(path, count=3):
    tests = []
    for index in range(count):
        tests.append(
            {
                "test_id": f"TEST_{index}",
                "category": "Legacy category",
                "requirement_category": "Protocol" if index < 2 else "Security",
                "requirement_subcategory": (
                    "Transfers" if index == 0 else "Timing" if index == 1 else "Access"
                ),
            }
        )
    path.write_text(json.dumps({"metadata": {}, "feature_list": tests}))


def test_hierarchical_subcategories_receive_independent_priorities(tmp_path):
    vplan = tmp_path / "vplan.json"
    _write_vplan(vplan)

    output = prioritise_vplan(
        vplan_file=vplan,
        priority_1_categories=["Protocol::Transfers"],
        priority_2_categories=["Security::Access"],
        output_dir=tmp_path / "output",
    )

    result = json.loads(output.read_text())
    priorities = {item["test_id"]: item["priority"] for item in result["feature_list"]}
    assert priorities == {"TEST_0": 1, "TEST_2": 2, "TEST_1": 3}


def test_priority_selection_limit_is_larger_but_still_bounded(tmp_path):
    vplan = tmp_path / "vplan.json"
    _write_vplan(vplan, count=MAX_PRIORITY_SELECTIONS + 1)

    with pytest.raises(ValueError, match=f"no more than {MAX_PRIORITY_SELECTIONS}"):
        prioritise_vplan(
            vplan_file=vplan,
            priority_1_categories=[f"Selection {index}" for index in range(2)],
            priority_2_categories=[
                f"Selection {index}" for index in range(2, MAX_PRIORITY_SELECTIONS + 1)
            ],
            output_dir=tmp_path / "output",
        )
