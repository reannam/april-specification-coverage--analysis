import json
from pathlib import Path

import pytest

from Backend.report_generation import weak_language_check as wlc

# ---------------------------------------------------------------------------
# unwrap_requirements
# ---------------------------------------------------------------------------


def test_unwrap_requirements_accepts_raw_list(mixed_requirements):
    result = wlc.unwrap_requirements(mixed_requirements)

    assert result == mixed_requirements


def test_unwrap_requirements_accepts_dict_with_requirements_key(
    requirements_wrapped_dict,
    mixed_requirements,
):
    result = wlc.unwrap_requirements(requirements_wrapped_dict)

    assert result == mixed_requirements


def test_unwrap_requirements_returns_empty_list_when_dict_has_no_requirements_key():
    result = wlc.unwrap_requirements({"metadata": {"name": "No requirements"}})

    assert result == []


@pytest.mark.parametrize(
    "invalid_input",
    [
        "not a requirements list",
        123,
        None,
        {"requirements": "not a list"},
        {"requirements": {"REQ_001": "bad structure"}},
    ],
)
def test_unwrap_requirements_raises_value_error_for_invalid_input(invalid_input):
    with pytest.raises(ValueError, match="Expected requirements to be a list"):
        wlc.unwrap_requirements(invalid_input)


# ---------------------------------------------------------------------------
# get_requirement_display_text
# ---------------------------------------------------------------------------


def test_get_requirement_display_text_combines_text_and_description():
    requirement = {
        "description": "The Core MUST Reset.",
        "text": "The Signal SHALL Be Low.",
    }

    result = wlc.get_requirement_display_text(requirement)

    assert result.startswith("The Signal SHALL Be Low.")
    assert "The Core MUST Reset." in result


def test_get_requirement_display_text_handles_missing_fields():
    requirement = {"id": "REQ_I2C_001"}

    result = wlc.get_requirement_display_text(requirement)

    assert result == ""


def test_get_requirement_display_text_casts_non_string_values_to_string():
    requirement = {
        "description": 123,
        "text": None,
    }

    result = wlc.get_requirement_display_text(requirement)

    assert result == "123"


# ---------------------------------------------------------------------------
# contains_word_or_phrase
# ---------------------------------------------------------------------------


def test_contains_word_or_phrase_returns_true_for_word_match():
    text = "the controller must reset correctly"

    result = wlc.contains_word_or_phrase(text, ["must", "shall"])

    assert result is True


def test_contains_word_or_phrase_returns_true_for_phrase_match():
    text = "the behaviour is implementation defined"

    result = wlc.contains_word_or_phrase(text, ["implementation defined"])

    assert result is True


def test_contains_word_or_phrase_returns_false_when_no_match():
    text = "the controller resets correctly"

    result = wlc.contains_word_or_phrase(text, ["must", "shall"])

    assert result is False


def test_contains_word_or_phrase_returns_false_for_empty_word_list():
    result = wlc.contains_word_or_phrase("the controller must reset", [])

    assert result is False


def test_contains_word_or_phrase_uses_word_boundaries():
    result = wlc.contains_word_or_phrase("the signal is canonical", ["can"])

    assert result is False


# ---------------------------------------------------------------------------
# check_requirement_language
# ---------------------------------------------------------------------------


def test_check_requirement_language_returns_no_issues_for_strong_requirements(
    strong_requirements,
):
    result = wlc.check_requirement_language(strong_requirements)

    assert result == []


def test_check_requirement_language_flags_weak_language(weak_requirements):
    result = wlc.check_requirement_language(weak_requirements)

    weak_language_issues = [
        issue for issue in result if issue["issue_type"] == "weak_or_optional_language"
    ]

    assert len(weak_language_issues) == 2

    first_issue = weak_language_issues[0]
    second_issue = weak_language_issues[1]

    assert first_issue["requirement_id"] == "REQ_I2C_003"
    assert "should" in first_issue["matched_words"]
    assert "may" in first_issue["matched_words"]
    assert "where supported" in first_issue["matched_words"]

    assert second_issue["requirement_id"] == "REQ_I2C_004"
    assert "can" in second_issue["matched_words"]
    assert "as appropriate" in second_issue["matched_words"]
    assert "implementation-defined" in second_issue["matched_words"]


def test_check_requirement_language_flags_missing_strong_language(weak_requirements):
    result = wlc.check_requirement_language(weak_requirements)

    missing_strong_issues = [
        issue
        for issue in result
        if issue["issue_type"] == "missing_strong_requirement_language"
    ]

    assert len(missing_strong_issues) == 2
    assert {issue["requirement_id"] for issue in missing_strong_issues} == {
        "REQ_I2C_003",
        "REQ_I2C_004",
    }


def test_check_requirement_language_accepts_wrapped_dict(requirements_wrapped_dict):
    result = wlc.check_requirement_language(requirements_wrapped_dict)

    assert isinstance(result, list)
    assert len(result) == 4


def test_check_requirement_language_skips_non_dict_items():
    requirements = [
        {
            "id": "REQ_I2C_001",
            "description": "The controller must reset.",
            "text": "The controller shall reset.",
        },
        "bad item",
        123,
        None,
    ]

    result = wlc.check_requirement_language(requirements)

    assert result == []


def test_check_requirement_language_uses_unknown_id_when_missing():
    requirements = [
        {
            "description": "The controller may support optional reset.",
            "text": "Reset can be implementation defined.",
        }
    ]

    result = wlc.check_requirement_language(requirements)

    assert len(result) == 2
    assert all(issue["requirement_id"] == "UNKNOWN" for issue in result)


def test_check_requirement_language_flags_weak_even_when_strong_language_exists():
    requirements = [
        {
            "id": "REQ_I2C_001",
            "description": "The controller must support reset where applicable.",
            "text": "The reset behaviour shall be configurable.",
        }
    ]

    result = wlc.check_requirement_language(requirements)

    assert len(result) == 1
    assert result[0]["requirement_id"] == "REQ_I2C_001"
    assert result[0]["issue_type"] == "weak_or_optional_language"
    assert "where applicable" in result[0]["matched_words"]
    assert "configurable" in result[0]["matched_words"]


def test_check_requirement_language_flags_missing_strong_when_no_strong_or_weak_words():
    requirements = [
        {
            "id": "REQ_I2C_001",
            "description": "The controller resets after power on.",
            "text": "The reset signal is low.",
        }
    ]

    result = wlc.check_requirement_language(requirements)

    assert len(result) == 1

    issue = result[0]

    assert issue["requirement_id"] == "REQ_I2C_001"
    assert issue["source_section"] == "I2"
    assert issue["requirement_text"].startswith("The reset signal is low.")
    assert "The controller resets after power on." in issue["requirement_text"]
    assert issue["issue_type"] == "missing_strong_requirement_language"
    assert issue["message"] == (
        "Requirement does not contain strong requirement wording "
        "such as must, shall, should, required, or requires."
    )


def test_check_requirement_language_finds_weak_words_from_description_and_text():
    requirements = [
        {
            "id": "REQ_I2C_001",
            "description": "The controller should support reset.",
            "text": "The controller may support interrupt generation.",
        }
    ]

    result = wlc.check_requirement_language(requirements)

    weak_issue = next(
        issue for issue in result if issue["issue_type"] == "weak_or_optional_language"
    )

    assert "should" in weak_issue["matched_words"]
    assert "may" in weak_issue["matched_words"]


@pytest.mark.parametrize("weak_phrase", wlc.WEAK_REQUIREMENT_WORDS)
def test_check_requirement_language_detects_each_weak_phrase(weak_phrase):
    requirements = [
        {
            "id": "REQ_TEST_001",
            "description": f"The controller {weak_phrase} reset behaviour.",
            "text": "",
        }
    ]

    result = wlc.check_requirement_language(requirements)

    weak_issues = [
        issue for issue in result if issue["issue_type"] == "weak_or_optional_language"
    ]

    assert len(weak_issues) == 1
    assert weak_phrase in weak_issues[0]["matched_words"]


@pytest.mark.parametrize("strong_word", wlc.STRONG_REQUIREMENT_WORDS)
def test_check_requirement_language_detects_each_strong_word(strong_word):
    requirements = [
        {
            "id": "REQ_TEST_001",
            "description": f"The controller {strong_word} reset behaviour.",
            "text": "",
        }
    ]

    result = wlc.check_requirement_language(requirements)

    missing_strong_issues = [
        issue
        for issue in result
        if issue["issue_type"] == "missing_strong_requirement_language"
    ]

    assert missing_strong_issues == []


# ---------------------------------------------------------------------------
# save_requirement_language_report
# ---------------------------------------------------------------------------


def test_save_requirement_language_report_writes_expected_json(tmp_path):
    issues = [
        {
            "requirement_id": "REQ_I2C_001",
            "issue_type": "weak_or_optional_language",
            "matched_words": ["should"],
            "message": "Example message",
        }
    ]

    output_file = tmp_path / "language-report.json"

    wlc.save_requirement_language_report(issues, output_file)

    saved_data = json.loads(output_file.read_text(encoding="utf-8"))

    assert saved_data == {
        "source_file": None,
        "number_of_language_issues": 1,
        "issues": issues,
    }


def test_save_requirement_language_report_accepts_string_path(tmp_path):
    issues = []
    output_file = tmp_path / "language-report.json"

    wlc.save_requirement_language_report(issues, str(output_file))

    saved_data = json.loads(output_file.read_text(encoding="utf-8"))

    assert saved_data == {
        "source_file": None,
        "number_of_language_issues": 0,
        "issues": [],
    }


def test_save_requirement_language_report_prints_output_path(tmp_path, capsys):
    output_file = tmp_path / "language-report.json"

    wlc.save_requirement_language_report([], output_file)

    captured = capsys.readouterr()

    assert f"Requirement language report saved to {output_file}" in captured.out


# ---------------------------------------------------------------------------
# print_requirement_language_summary
# ---------------------------------------------------------------------------


def test_print_requirement_language_summary_for_no_issues(capsys):
    wlc.print_requirement_language_summary([])

    captured = capsys.readouterr()

    assert "Requirement language check" in captured.out
    assert "Language issues found: 0" in captured.out
    assert "No weak or unclear requirement language found." in captured.out


def test_print_requirement_language_summary_for_weak_language_issue(capsys):
    issues = [
        {
            "requirement_id": "REQ_I2C_001",
            "issue_type": "weak_or_optional_language",
            "matched_words": ["should", "may"],
            "message": "Example message",
        }
    ]

    wlc.print_requirement_language_summary(issues)

    captured = capsys.readouterr()

    assert "Language issues found: 1" in captured.out
    assert "- REQ_I2C_001: weak language found (should, may)" in captured.out


def test_print_requirement_language_summary_for_missing_strong_issue(capsys):
    issues = [
        {
            "requirement_id": "REQ_I2C_001",
            "issue_type": "missing_strong_requirement_language",
            "message": "Example message",
        }
    ]

    wlc.print_requirement_language_summary(issues)

    captured = capsys.readouterr()

    assert "Language issues found: 1" in captured.out
    assert "- REQ_I2C_001: missing strong requirement language" in captured.out


def test_print_requirement_language_summary_for_mixed_issues(capsys):
    issues = [
        {
            "requirement_id": "REQ_I2C_001",
            "issue_type": "weak_or_optional_language",
            "matched_words": ["should"],
            "message": "Example message",
        },
        {
            "requirement_id": "REQ_I2C_002",
            "issue_type": "missing_strong_requirement_language",
            "message": "Example message",
        },
    ]

    wlc.print_requirement_language_summary(issues)

    captured = capsys.readouterr()

    assert "Language issues found: 2" in captured.out
    assert "- REQ_I2C_001: weak language found (should)" in captured.out
    assert "- REQ_I2C_002: missing strong requirement language" in captured.out


# ---------------------------------------------------------------------------
# get_flagged_requirements
# ---------------------------------------------------------------------------


def test_get_flagged_requirements_returns_only_requirements_with_issues(
    mixed_requirements,
):
    language_issues = [
        {
            "requirement_id": "REQ_I2C_003",
            "issue_type": "weak_or_optional_language",
        },
        {
            "requirement_id": "REQ_I2C_004",
            "issue_type": "missing_strong_requirement_language",
        },
    ]

    result = wlc.get_flagged_requirements(mixed_requirements, language_issues)

    assert [requirement["id"] for requirement in result] == [
        "REQ_I2C_003",
        "REQ_I2C_004",
    ]


def test_get_flagged_requirements_accepts_wrapped_dict(requirements_wrapped_dict):
    language_issues = [
        {
            "requirement_id": "REQ_I2C_003",
            "issue_type": "weak_or_optional_language",
        }
    ]

    result = wlc.get_flagged_requirements(requirements_wrapped_dict, language_issues)

    assert len(result) == 1
    assert result[0]["id"] == "REQ_I2C_003"


def test_get_flagged_requirements_deduplicates_issue_ids(mixed_requirements):
    language_issues = [
        {
            "requirement_id": "REQ_I2C_003",
            "issue_type": "weak_or_optional_language",
        },
        {
            "requirement_id": "REQ_I2C_003",
            "issue_type": "missing_strong_requirement_language",
        },
    ]

    result = wlc.get_flagged_requirements(mixed_requirements, language_issues)

    assert len(result) == 1
    assert result[0]["id"] == "REQ_I2C_003"


def test_get_flagged_requirements_returns_empty_list_when_no_ids_match(
    mixed_requirements,
):
    language_issues = [
        {
            "requirement_id": "REQ_DOES_NOT_EXIST",
            "issue_type": "weak_or_optional_language",
        }
    ]

    result = wlc.get_flagged_requirements(mixed_requirements, language_issues)

    assert result == []


# ---------------------------------------------------------------------------
# run_weak_language_checker
# ---------------------------------------------------------------------------


def test_run_weak_language_checker_creates_report_file(
    extracted_requirements_file,
):
    result_path = wlc.run_weak_language_checker(str(extracted_requirements_file))

    assert isinstance(result_path, Path)
    assert result_path.exists()
    assert result_path.name.startswith("weak_words_")
    assert result_path.name.endswith(".json")

    saved_data = json.loads(result_path.read_text(encoding="utf-8"))

    assert saved_data["number_of_language_issues"] == 4
    assert len(saved_data["issues"]) == 4

    result_path.unlink()


def test_run_weak_language_checker_accepts_wrapped_requirements_file(
    wrapped_requirements_file,
):
    result_path = wlc.run_weak_language_checker(str(wrapped_requirements_file))

    assert result_path.exists()

    saved_data = json.loads(result_path.read_text(encoding="utf-8"))

    assert saved_data["number_of_language_issues"] == 4
    assert len(saved_data["issues"]) == 4

    result_path.unlink()


def test_run_weak_language_checker_prints_summary_and_file_path(
    extracted_requirements_file,
    capsys,
):
    result_path = wlc.run_weak_language_checker(str(extracted_requirements_file))

    captured = capsys.readouterr()

    assert f"Using requirements file: {extracted_requirements_file}" in captured.out
    assert f"Requirement language report saved to {result_path}" in captured.out
    assert "Requirement language check" in captured.out
    assert "Language issues found: 4" in captured.out

    result_path.unlink()


def test_run_weak_language_checker_raises_for_missing_file(tmp_path):
    missing_file = tmp_path / "does-not-exist.json"

    with pytest.raises(FileNotFoundError):
        wlc.run_weak_language_checker(str(missing_file))


def test_run_weak_language_checker_raises_for_malformed_json(malformed_json_file):
    with pytest.raises(json.JSONDecodeError):
        wlc.run_weak_language_checker(str(malformed_json_file))


def test_run_weak_language_checker_raises_for_empty_json_file(empty_json_file):
    with pytest.raises(json.JSONDecodeError):
        wlc.run_weak_language_checker(str(empty_json_file))


def test_run_weak_language_checker_raises_for_invalid_json_shape(tmp_path):
    invalid_file = tmp_path / "invalid-shape.json"
    invalid_file.write_text(json.dumps({"requirements": "bad"}), encoding="utf-8")

    with pytest.raises(ValueError, match="Expected requirements to be a list"):
        wlc.run_weak_language_checker(str(invalid_file))
