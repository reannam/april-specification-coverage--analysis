import json

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover - compatibility with older PyMuPDF
    import fitz
import pytest

from Backend.Extraction.extractor import parse_pdf
from Backend.Extraction.requirements import write_requirements_file


def test_parse_pdf_writes_full_and_requirements_outputs(tmp_path):
    pdf_path = tmp_path / "source.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "A2 Interface behaviour")
    page.insert_text((72, 100), "The controller must remain stable during transfer.")
    pdf.save(pdf_path)
    pdf.close()

    result = parse_pdf(
        pdf_path,
        tmp_path / "outputs",
        output_stem="run_123",
        document_name="source.pdf",
    )

    assert result["document_path"].name == "run_123_document.json"
    assert result["document"]["document_name"] == "source.pdf"
    assert result["document"]["requirements"][0]["id"].startswith("REQ_A2_")

    saved_document = json.loads(result["document_path"].read_text())
    assert saved_document["requirements"] == result["document"]["requirements"]


def test_requirements_file_rejects_records_without_text(tmp_path):
    source = tmp_path / "document.json"
    source.write_text(json.dumps({"requirements": [{"id": "REQ_1"}]}))

    with pytest.raises(ValueError, match="non-empty text"):
        write_requirements_file(source, output_dir=tmp_path / "outputs")


def test_requirements_file_preserves_engineering_fields(tmp_path):
    source = tmp_path / "document.json"
    requirement = {
        "id": "REQ_A2_001",
        "text": "The interface shall assert READY.",
        "source_section": "A2",
        "source_page": 4,
        "signals": ["READY"],
        "type": "protocol_rule",
    }
    source.write_text(
        json.dumps({"document_name": "spec.pdf", "requirements": [requirement]})
    )

    result = write_requirements_file(source, output_dir=tmp_path / "outputs")

    assert result["document"]["requirements"] == [requirement]
    assert result["document"]["refinement_summary"] == {
        "input_requirements": 1,
        "vplan_relevant_requirements": 1,
        "excluded_requirements": 0,
    }
    assert result["output_path"].is_file()


def test_requirements_file_excludes_non_vplan_descriptions(tmp_path):
    source = tmp_path / "document.json"
    source.write_text(
        json.dumps(
            {
                "requirements": [
                    {"id": "REQ_1", "text": "This chapter describes the interface."},
                    {"id": "REQ_2", "text": "The interface shall assert READY."},
                ]
            }
        )
    )

    result = write_requirements_file(source, output_dir=tmp_path / "outputs")

    assert [item["id"] for item in result["document"]["requirements"]] == ["REQ_2"]
    assert result["document"]["refinement_summary"]["excluded_requirements"] == 1
