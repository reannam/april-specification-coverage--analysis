import json
from copy import deepcopy
from pathlib import Path

from Backend.agents import edge_case_agent


class FakeEdgeCases:
    def __init__(self):
        self.edge_cases = [
            {
                "edge_case_id": "EDGE_REQ_I2C_001",
                "requirement_id": "REQ_I2C_001",
                "edge_case_type": "optional_behaviour",
                "edge_case_description": "Requirement uses optional wording.",
            }
        ]

    def model_dump(self):
        # Return a copy because edge_case_agent_call may enrich the dictionaries.
        return {"edge_cases": deepcopy(self.edge_cases)}


def test_edge_case_agent_call_creates_edge_case_report(
    tmp_path,
    monkeypatch,
):
    requirements_file = tmp_path / "requirements.json"
    requirements_file.write_text(
        json.dumps(
            {
                "requirements": [
                    {
                        "id": "REQ_I2C_001",
                        "description": ("The controller may support fast mode."),
                        "text": "Fast mode may be supported.",
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "edge_case_outputs"
    output_dir.mkdir()

    weak_language_file = tmp_path / "weak-language.json"
    weak_language_file.write_text("{}", encoding="utf-8")

    fake_issues = [
        {
            "requirement_id": "REQ_I2C_001",
            "requirement_text": (
                "Fast mode may be supported. " "The controller may support fast mode."
            ),
            "source_section": "I2",
            "issue_type": "weak_or_optional_language",
            "matched_words": ["may"],
        }
    ]

    fake_flagged_requirements = [
        {
            "id": "REQ_I2C_001",
            "description": ("The controller may support fast mode."),
            "text": "Fast mode may be supported.",
        }
    ]

    expected_edge_case = {
        "edge_case_id": "EDGE_REQ_I2C_001",
        "requirement_id": "REQ_I2C_001",
        "edge_case_type": "optional_behaviour",
        "edge_case_description": ("Requirement uses optional wording."),
    }

    def fake_run_weak_language_checker(requirements):
        assert requirements == str(requirements_file)
        return weak_language_file

    def fake_check_requirement_language(input_requirements):
        assert input_requirements == [
            {
                "id": "REQ_I2C_001",
                "description": ("The controller may support fast mode."),
                "text": "Fast mode may be supported.",
            }
        ]
        return fake_issues

    def fake_get_flagged_requirements(
        requirements,
        language_issues,
    ):
        assert language_issues == fake_issues
        return fake_flagged_requirements

    def fake_extract_edge_cases(
        flagged_requirements,
        language_issues,
        requirements_file_name,
    ):
        assert flagged_requirements == fake_flagged_requirements
        assert language_issues == fake_issues
        assert requirements_file_name == "requirements.json"

        return (
            FakeEdgeCases(),
            {"total_tokens": 10},
            "fake-trace-id",
        )

    monkeypatch.setattr(
        edge_case_agent,
        "EDGE_CASE_DIR",
        output_dir,
    )
    monkeypatch.setattr(
        edge_case_agent,
        "run_weak_language_checker",
        fake_run_weak_language_checker,
    )
    monkeypatch.setattr(
        edge_case_agent,
        "check_requirement_language",
        fake_check_requirement_language,
    )
    monkeypatch.setattr(
        edge_case_agent,
        "get_flagged_requirements",
        fake_get_flagged_requirements,
    )
    monkeypatch.setattr(
        edge_case_agent,
        "extract_edge_cases",
        fake_extract_edge_cases,
    )

    # Call the function once.
    result = edge_case_agent.edge_case_agent_call(str(requirements_file))

    assert result["edge_case_trace_id"] == "fake-trace-id"
    assert result["edge_case_usage"] == {"total_tokens": 10}

    assert result["weak_words_file"] == str(weak_language_file)

    actual_edge_cases = result["edge_cases"]["edge_cases"]

    assert len(actual_edge_cases) == 1

    actual_edge_case = actual_edge_cases[0]

    # The generated fields must remain unchanged.
    for key, expected_value in expected_edge_case.items():
        assert actual_edge_case[key] == expected_value

    # Context is added by edge_case_agent_call.
    assert actual_edge_case["requirement_text"] == (
        "Fast mode may be supported. " "The controller may support fast mode."
    )
    assert actual_edge_case["source_section"] == "I2"

    output_file = Path(result["edge_case_output_file"])

    assert output_file.exists()
    assert output_file.parent == output_dir

    saved_data = json.loads(output_file.read_text(encoding="utf-8"))

    assert saved_data["edge_cases"] == actual_edge_cases

    metadata = saved_data["metadata"]

    assert metadata["requirements_file"] == str(requirements_file)
    assert metadata["weak_language_file"] == str(weak_language_file)
    assert metadata["total_requirements"] == 1
    assert metadata["number_of_weak_language_instances"] == 1
    assert metadata["number_of_flagged_requirements"] == 1
    assert metadata["number_of_edge_case_candidates"] == 1
    assert metadata["langsmith_trace_id"] == "fake-trace-id"
