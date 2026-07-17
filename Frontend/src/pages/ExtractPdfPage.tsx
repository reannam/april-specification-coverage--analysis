import { useState } from "react";
import { Link } from "react-router-dom";

import DownloadCard from "../components/common/DownloadCard";
import FileUpload from "../components/common/FileUpload";
import PageHeader from "../components/common/PageHeader";
import StatusPanel from "../components/common/StatusPanel";
import { useWorkflow } from "../context/WorkflowContext";
import { postFormData } from "../services/api";
import type { PdfExtractionResponse } from "../types/workflow";
import { humaniseLabel } from "../utils/formatters";

type RunStatus = "idle" | "processing" | "error";

export default function ExtractPdfPage() {
  const { setExtractedDocumentFilename, setExtractedDocumentPath } = useWorkflow();
  const [sourcePdf, setSourcePdf] = useState<File | null>(null);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<PdfExtractionResponse | null>(null);

  const extract = async () => {
    if (!sourcePdf) return;
    setStatus("processing");
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("source_pdf", sourcePdf);
      const response = await postFormData<PdfExtractionResponse>(
        "/api/extract-pdf",
        formData,
      );
      setExtractedDocumentPath(response.document_file);
      setExtractedDocumentFilename(response.document_filename);
      setResult(response);
      setStatus("idle");
    } catch (requestError) {
      setStatus("error");
      setError(
        requestError instanceof Error ? requestError.message : "PDF extraction failed.",
      );
    }
  };

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Prepare"
        title="Extract from PDF"
        description="Extract the complete hardware or software specification into structured document JSON. Requirements are refined in the next stage."
      />

      <section className="panel">
        <FileUpload
          label="Source specification PDF"
          description="Select a text-based PDF specification"
          file={sourcePdf}
          onChange={setSourcePdf}
          accept=".pdf,application/pdf"
          disabled={status === "processing"}
        />
        <button
          className="button primary"
          disabled={!sourcePdf || status === "processing"}
          onClick={extract}
          type="button"
        >
          Extract specification
        </button>

        {status === "processing" ? (
          <StatusPanel
            status="processing"
            message="Reading pages, headings, requirements, tables, and references…"
          />
        ) : null}
        {status === "error" ? <StatusPanel status="error" message={error} /> : null}
      </section>

      {result ? (
        <section className="report-section">
          <div className="section-heading">
            <div>
              <h2>Extraction results</h2>
              <p>
                The complete document is ready. Continue to Extract requirements to
                refine it into the content used by vPlan generation.
              </p>
            </div>
            <Link className="button secondary" to="/prepare/requirements">
              Continue to Extract requirements
            </Link>
          </div>

          <div className="metric-grid">
            {Object.entries(result.summary).map(([name, value]) => (
              <article className="metric-card" key={name}>
                <span>{humaniseLabel(name)}</span>
                <strong>{String(value ?? "Not provided")}</strong>
              </article>
            ))}
          </div>

          <div className="download-grid">
            <DownloadCard
              title="Complete extracted document"
              filename={result.document_filename}
              url={result.document_download_url}
            />
          </div>
        </section>
      ) : null}
    </div>
  );
}
