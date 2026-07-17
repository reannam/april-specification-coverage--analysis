import { useState } from "react";
import { Link } from "react-router-dom";

import DownloadCard from "../components/common/DownloadCard";
import FileUpload from "../components/common/FileUpload";
import PageHeader from "../components/common/PageHeader";
import ReadableRecords from "../components/common/ReadableRecords";
import StatusPanel from "../components/common/StatusPanel";
import { useWorkflow } from "../context/WorkflowContext";
import { postFormData } from "../services/api";
import type { RequirementsExtractionResponse } from "../types/workflow";

type RunStatus = "idle" | "processing" | "error";

export default function ExtractRequirementsPage() {
  const {
    extractedDocumentFilename,
    extractedDocumentPath,
    setRequirementsData,
    setRequirementsFile,
  } = useWorkflow();
  const [extractedJson, setExtractedJson] = useState<File | null>(null);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<RequirementsExtractionResponse | null>(null);

  const extract = async () => {
    if (!extractedJson && !extractedDocumentPath) return;
    setStatus("processing");
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      if (extractedJson) {
        formData.append("extracted_json", extractedJson);
      } else if (extractedDocumentPath) {
        formData.append("extracted_path", extractedDocumentPath);
      }
      const response = await postFormData<RequirementsExtractionResponse>(
        "/api/extract-requirements",
        formData,
      );
      const requirementsFile = new File(
        [JSON.stringify(response.requirements_document, null, 2)],
        response.requirements_filename,
        { type: "application/json" },
      );
      setRequirementsFile(requirementsFile);
      setRequirementsData(response.requirements_document);
      setResult(response);
      setStatus("idle");
    } catch (requestError) {
      setStatus("error");
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Requirements extraction failed.",
      );
    }
  };

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Prepare"
        title="Extract requirements"
        description="Create the compact requirements JSON consumed by vPlan generation from a complete extracted document."
      />

      <section className="panel">
        {extractedDocumentPath && !extractedJson ? (
          <section className="notice">
            <strong>Complete extraction selected</strong>
            <p>
              {extractedDocumentFilename ?? "The document from PDF extraction"} will
              be refined. Upload a file below only if you want to replace it.
            </p>
          </section>
        ) : null}
        <FileUpload
          label="Complete extracted document"
          description="Select document JSON produced by PDF extraction"
          file={extractedJson}
          onChange={setExtractedJson}
          disabled={status === "processing"}
        />
        <button
          className="button primary"
          disabled={
            (!extractedJson && !extractedDocumentPath) || status === "processing"
          }
          onClick={extract}
          type="button"
        >
          Extract requirements
        </button>

        {status === "processing" ? (
          <StatusPanel status="processing" message="Validating and preparing requirements…" />
        ) : null}
        {status === "error" ? <StatusPanel status="error" message={error} /> : null}
      </section>

      {result ? (
        <section className="report-section">
          <div className="section-heading">
            <div>
              <h2>{result.requirement_count} requirements ready</h2>
              <p>The generated file is selected automatically for vPlan generation.</p>
            </div>
            <Link className="button secondary" to="/verification/generate">
              Continue to vPlan
            </Link>
          </div>
          <div className="download-grid">
            <DownloadCard
              title="Requirements for vPlan"
              filename={result.requirements_filename}
              url={result.requirements_download_url}
            />
          </div>
          {result.requirements_document.refinement_summary ? (
            <div className="metric-grid">
              <article className="metric-card">
                <span>Input requirements</span>
                <strong>
                  {result.requirements_document.refinement_summary.input_requirements}
                </strong>
              </article>
              <article className="metric-card">
                <span>Retained for vPlan</span>
                <strong>
                  {
                    result.requirements_document.refinement_summary
                      .vplan_relevant_requirements
                  }
                </strong>
              </article>
              <article className="metric-card">
                <span>Excluded as non-vPlan content</span>
                <strong>
                  {
                    result.requirements_document.refinement_summary
                      .excluded_requirements
                  }
                </strong>
              </article>
            </div>
          ) : null}
          <ReadableRecords
            records={result.requirements_document.requirements}
            idKeys={["id", "text"]}
            empty="No requirements were provided."
          />
        </section>
      ) : null}
    </div>
  );
}
