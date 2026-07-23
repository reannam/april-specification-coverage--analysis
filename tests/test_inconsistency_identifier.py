import json
from types import SimpleNamespace

from Backend.AnalyseAndCompareSpecs.inconsistency_identifier import (
    build_consensus,
    normalise_finding_key,
    run_inconsistency_check,
)


def finding(*, reverse=False, confidence="High"):
    record = {
        "title": "Reserved value has active meaning",
        "entity": "MXL field",
        "category": "Reserved Value Contradiction",
        "page_a": 27,
        "page_b": 28,
        "section_a": "Table 11",
        "section_b": "3.1.1",
        "statement_a": "MXL=3 is reserved.",
        "statement_b": "The formula assigns MXL=3 a width.",
        "reason": "A reserved value cannot simultaneously have an active meaning.",
        "confidence": confidence,
    }
    if reverse:
        for suffix in ("page", "section", "statement"):
            record[f"{suffix}_a"], record[f"{suffix}_b"] = (
                record[f"{suffix}_b"],
                record[f"{suffix}_a"],
            )
    return record


def test_finding_key_is_independent_of_statement_order():
    assert normalise_finding_key(finding()) == normalise_finding_key(
        finding(reverse=True)
    )


def test_consensus_requires_distinct_reviewer_votes():
    result, unique_findings = build_consensus(
        [[finding(), finding()], [finding(reverse=True)], []],
        majority_threshold=2,
    )

    assert unique_findings == 1
    assert result[0]["agent_votes"] == 2


class FakeFiles:
    def __init__(self):
        self.deleted = []

    def create(self, **_kwargs):
        return SimpleNamespace(id="uploaded_pdf")

    def delete(self, file_id):
        self.deleted.append(file_id)


class FakeResponses:
    def __init__(self):
        self.calls = 0

    def create(self, **_kwargs):
        self.calls += 1
        findings = [finding(reverse=self.calls % 2 == 0)] if self.calls <= 4 else []
        return SimpleNamespace(
            output_text=json.dumps({"inconsistencies": findings}),
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
            ),
        )


class FakeClient:
    def __init__(self):
        self.files = FakeFiles()
        self.responses = FakeResponses()


def test_full_check_writes_consensus_and_deletes_uploaded_file(tmp_path):
    pdf_path = tmp_path / "spec.pdf"
    pdf_path.write_bytes(b"fake PDF bytes are sufficient for the injected client")
    client = FakeClient()

    result = run_inconsistency_check(
        pdf_path,
        output_dir=tmp_path / "reports",
        number_of_agents=6,
        client=client,
    )

    assert result["report_path"].is_file()
    assert result["report"]["metadata"]["consensus_findings"] == 1
    assert result["report"]["inconsistencies"][0]["agent_votes"] == 4
    assert result["report"]["metadata"]["usage"]["total_tokens"] == 90
    assert client.files.deleted == ["uploaded_pdf"]
