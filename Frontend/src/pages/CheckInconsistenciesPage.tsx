import { useMemo, useState } from "react";

import DownloadCard from "../components/common/DownloadCard";
import FileUpload from "../components/common/FileUpload";
import PageHeader from "../components/common/PageHeader";
import ReadableRecords from "../components/common/ReadableRecords";
import StatusPanel from "../components/common/StatusPanel";
import { postFormData } from "../services/api";
import type { InconsistencyResponse } from "../types/workflow";

type RunStatus = "idle" | "processing" | "error";

export default function CheckInconsistenciesPage() {
  const [specificationPdf, setSpecificationPdf] = useState<File | null>(null);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<InconsistencyResponse | null>(null);

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const finding of result?.report.inconsistencies ?? []) {
      counts[finding.category] = (counts[finding.category] ?? 0) + 1;
    }
    return counts;
  }, [result]);

  const runCheck = async () => {
    if (!specificationPdf) return;
    setStatus("processing");
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("specification_pdf", specificationPdf);
      const response = await postFormData<InconsistencyResponse>(
        "/api/check-inconsistencies",
        formData,
      );
      setResult(response);
      setStatus("idle");
    } catch (requestError) {
      setStatus("error");
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Inconsistency analysis failed.",
      );
    }
  };

  const metadata = result?.report.metadata;

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Analyse and compare"
        title="Check for Inconsistencies"
        description="Run independent reviews of one complete specification and retain only contradictions that reach majority consensus."
      />

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Internal consistency review</h2>
            <p>
              This is a model-assisted PDF review. The default configuration runs
              six reviewers, so it can take several minutes and make six model calls.
            </p>
          </div>
        </div>
        <FileUpload
          label="Specification PDF"
          description="Select the complete PDF to inspect"
          file={specificationPdf}
          onChange={setSpecificationPdf}
          accept=".pdf,application/pdf"
          disabled={status === "processing"}
        />
        <button
          className="button primary"
          disabled={!specificationPdf || status === "processing"}
          onClick={runCheck}
          type="button"
        >
          {status === "processing" ? "Checking…" : "Check for inconsistencies"}
        </button>

        {status === "processing" ? (
          <StatusPanel
            status="processing"
            message="Running independent specification reviews and calculating consensus…"
          />
        ) : null}
        {status === "error" ? <StatusPanel status="error" message={error} /> : null}
      </section>

      {result && metadata ? (
        <section className="report-section">
          <div className="section-heading">
            <div>
              <h2>Consensus results</h2>
              <p>
                Findings are candidates for engineering review, not proven defects.
              </p>
            </div>
            <span className="pill">
              {metadata.consensus_findings} inconsistencies
            </span>
          </div>

          <div className="metric-grid">
            <article className="metric-card">
              <span>Successful reviewers</span>
              <strong>
                {metadata.successful_reviewers}/{metadata.requested_reviewers}
              </strong>
            </article>
            <article className="metric-card">
              <span>Consensus threshold</span>
              <strong>{metadata.majority_threshold} votes</strong>
            </article>
            <article className="metric-card">
              <span>Candidate findings</span>
              <strong>{metadata.unique_candidate_findings}</strong>
            </article>
            <article className="metric-card">
              <span>Total tokens</span>
              <strong>{metadata.usage.total_tokens.toLocaleString()}</strong>
            </article>
          </div>

          {Object.keys(categoryCounts).length ? (
            <div className="chip-list" aria-label="Inconsistency categories">
              {Object.entries(categoryCounts).map(([category, count]) => (
                <span className="pill" key={category}>
                  {category}: {count}
                </span>
              ))}
            </div>
          ) : null}

          <div className="download-grid">
            <DownloadCard
              title="Consensus inconsistency report"
              filename={result.report_filename}
              url={result.report_download_url}
            />
          </div>

          <ReadableRecords
            records={result.report.inconsistencies}
            idKeys={["title", "entity"]}
            empty="No finding reached the configured majority threshold."
          />

          <details className="panel">
            <summary>Independent reviewer outputs</summary>
            <div className="download-grid">
              {result.reviewer_outputs.map((output, index) => (
                <DownloadCard
                  title={`Reviewer ${index + 1} output`}
                  filename={output.filename}
                  url={output.download_url}
                  key={output.filename}
                />
              ))}
            </div>
          </details>
        </section>
      ) : null}
    </div>
  );
}
