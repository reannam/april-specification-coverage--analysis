import json
from pathlib import Path

import pytest

from Backend.pre_processing import preprocess_requirements as pre


@pytest.fixture
def full_document_requirements_data(mixed_requirements) -> dict:
    return {
        "metadata": {
            "document_name": "Example I2C Full Specification",
            "version": "1.0",
        },
        "sections": [
            {
                "section_id": "1",
                "title": "Overview",
                "content": "Example specification content.",
            }
        ],
        "requirements": mixed_requirements,
    }


@pytest.fixture
def full_document_requirements_file(
    tmp_path: Path,
    full_document_requirements_data: dict,
) -> Path:
    file_path = tmp_path / "full-document.json"
    file_path.write_text(
        json.dumps(full_document_requirements_data, indent=2),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def document_without_requirements_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "document-without-requirements.json"
    file_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "document_name": "Invalid document",
                },
                "sections": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return file_path


def test_preprocess_requirements_file_creates_output_file(
    full_document_requirements_file,
):
    output_path = pre.preprocess_requirements_file(full_document_requirements_file)

    assert isinstance(output_path, Path)
    assert output_path.exists()
    assert output_path.name == "full-document_requirements_only.json"
    assert output_path.parent.name == "preprocessed"


def test_preprocess_requirements_file_outputs_only_requirements_key(
    full_document_requirements_file,
    mixed_requirements,
):
    output_path = pre.preprocess_requirements_file(full_document_requirements_file)

    output_data = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_data == {
        "requirements": mixed_requirements,
    }

    assert "metadata" not in output_data
    assert "sections" not in output_data


def test_preprocess_requirements_file_accepts_string_path(
    full_document_requirements_file,
):
    output_path = pre.preprocess_requirements_file(str(full_document_requirements_file))

    assert output_path.exists()
    assert output_path.name == "full-document_requirements_only.json"


def test_preprocess_requirements_file_creates_preprocessed_directory(
    full_document_requirements_file,
):
    preprocessed_dir = full_document_requirements_file.parent / "preprocessed"

    assert not preprocessed_dir.exists()

    output_path = pre.preprocess_requirements_file(full_document_requirements_file)

    assert preprocessed_dir.exists()
    assert preprocessed_dir.is_dir()
    assert output_path.parent == preprocessed_dir


def test_preprocess_requirements_file_overwrites_existing_output(
    full_document_requirements_file,
):
    output_path = pre.preprocess_requirements_file(full_document_requirements_file)

    output_path.write_text(
        json.dumps({"requirements": [{"id": "OLD"}]}, indent=2),
        encoding="utf-8",
    )

    output_path = pre.preprocess_requirements_file(full_document_requirements_file)

    output_data = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_data["requirements"][0]["id"] == "REQ_I2C_001"
    assert output_data["requirements"][0]["id"] != "OLD"


def test_preprocess_requirements_file_preserves_empty_requirements_list(tmp_path):
    input_file = tmp_path / "empty-requirements.json"
    input_file.write_text(
        json.dumps(
            {
                "metadata": {
                    "document_name": "Empty requirements document",
                },
                "requirements": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    output_path = pre.preprocess_requirements_file(input_file)

    output_data = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_data == {
        "requirements": [],
    }


def test_preprocess_requirements_file_preserves_non_list_requirements_current_behaviour(
    tmp_path,
):
    """
    Current behaviour: this function only checks that the key exists.
    It does not validate that requirements is actually a list.
    """
    input_file = tmp_path / "non-list-requirements.json"
    input_file.write_text(
        json.dumps(
            {
                "metadata": {
                    "document_name": "Bad requirements shape",
                },
                "requirements": {"REQ_I2C_001": "This is not a list."},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    output_path = pre.preprocess_requirements_file(input_file)

    output_data = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_data == {"requirements": {"REQ_I2C_001": "This is not a list."}}


def test_preprocess_requirements_file_preserves_unicode_characters(tmp_path):
    input_file = tmp_path / "unicode-requirements.json"
    input_file.write_text(
        json.dumps(
            {
                "metadata": {
                    "document_name": "Unicode requirements document",
                },
                "requirements": [
                    {
                        "id": "REQ_UNICODE_001",
                        "text": "The signal shall support μs timing constraints.",
                    }
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output_path = pre.preprocess_requirements_file(input_file)

    output_text = output_path.read_text(encoding="utf-8")
    output_data = json.loads(output_text)

    assert "μs" in output_text
    assert output_data["requirements"][0]["text"] == (
        "The signal shall support μs timing constraints."
    )


def test_preprocess_requirements_file_raises_for_missing_file(tmp_path):
    missing_file = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError, match="Requirements file not found"):
        pre.preprocess_requirements_file(missing_file)


def test_preprocess_requirements_file_raises_for_missing_requirements_key(
    document_without_requirements_file,
):
    with pytest.raises(KeyError, match="No 'requirements' section found"):
        pre.preprocess_requirements_file(document_without_requirements_file)


def test_preprocess_requirements_file_raises_for_malformed_json(malformed_json_file):
    with pytest.raises(json.JSONDecodeError):
        pre.preprocess_requirements_file(malformed_json_file)


def test_preprocess_requirements_file_raises_for_empty_json_file(empty_json_file):
    with pytest.raises(json.JSONDecodeError):
        pre.preprocess_requirements_file(empty_json_file)


def test_preprocess_requirements_file_raises_type_error_for_json_list(tmp_path):
    """
    Current behaviour: if the JSON root is a list, the expression
    `"requirements" not in data` is valid and becomes True, so the function
    raises KeyError rather than TypeError.
    """
    input_file = tmp_path / "list-root.json"
    input_file.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(KeyError, match="No 'requirements' section found"):
        pre.preprocess_requirements_file(input_file)
