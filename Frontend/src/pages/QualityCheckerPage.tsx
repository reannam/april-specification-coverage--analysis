import { useState } from "react";

import DownloadCard from "../components/common/DownloadCard";
import FileUpload from "../components/common/FileUpload";
import PageHeader from "../components/common/PageHeader";
import StatusPanel from "../components/common/StatusPanel";
import { postFormData } from "../services/api";
import type { QualityResponse } from "../types/workflow";
import { humaniseLabel } from "../utils/formatters";

type RunStatus = "idle" | "processing" | "error";

export default function QualityCheckerPage() {
  const [extractedJson, setExtractedJson] = useState<File | null>(null);
  const [sourcePdf, setSourcePdf] = useState<File | null>(null);
  const [goldJson, setGoldJson] = useState<File | null>(null);
  const [threshold, setThreshold] = useState(95);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<QualityResponse | null>(null);

  const checkQuality = async () => {
    if (!extractedJson) return;
    setStatus("processing");
    setError("");

    try {
      const formData = new FormData();
      formData.append("extracted_json", extractedJson);
      if (sourcePdf) formData.append("source_pdf", sourcePdf);
      if (goldJson) formData.append("gold_json", goldJson);
      formData.append("threshold", String(threshold));

      const response = await postFormData<QualityResponse>(
        "/api/check-specification-quality",
        formData,
      );
      setResult(response);
      setStatus("idle");
    } catch (requestError) {
      setStatus("error");
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Quality analysis failed.",
      );
    }
  };

  const quality = result?.quality_report;

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Check for inconsistencies"
        title="Quality checker"
        description="Assess extractor completeness and accuracy, including requirement, table, figure, and image capture."
      />

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Check extraction quality</h2>
            <p>
              The source PDF and manually checked gold JSON are optional but make
              accuracy scores more meaningful.
            </p>
          </div>
        </div>

        <div className="upload-grid">
          <FileUpload
            label="Extracted JSON"
            description="Required extractor document.json"
            file={extractedJson}
            onChange={setExtractedJson}
            disabled={status === "processing"}
          />
          <FileUpload
            label="Source PDF"
            description="Optional source specification"
            file={sourcePdf}
            onChange={setSourcePdf}
            accept=".pdf,application/pdf"
            disabled={status === "processing"}
          />
          <FileUpload
            label="Gold reference JSON"
            description="Optional manually checked extraction"
            file={goldJson}
            onChange={setGoldJson}
            disabled={status === "processing"}
          />
          <label className="field">
            <span>Pass threshold (%)</span>
            <input
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={threshold}
              onChange={(event) => setThreshold(Number(event.target.value))}
              disabled={status === "processing"}
            />
          </label>
        </div>

        <button
          className="button primary"
          disabled={!extractedJson || status === "processing"}
          onClick={checkQuality}
        >
          Check quality
        </button>

        {status === "processing" ? (
          <StatusPanel status="processing" message="Calculating quality scores…" />
        ) : null}
        {status === "error" ? (
          <StatusPanel status="error" message={error} />
        ) : null}
      </section>

      {quality && result ? (
        <section className="report-section">
          <div className="section-heading">
            <div>
              <h2>Quality results</h2>
              <p>
                Each component is compared with the selected {threshold}% threshold.
              </p>
            </div>
            <span
              className={`pill ${quality.overall_status === "pass" ? "success" : "danger"}`}
            >
              Overall {quality.overall_percentage.toFixed(2)}% — {quality.overall_status}
            </span>
          </div>

          <div className="metric-grid">
            {Object.entries(quality.scores).map(([name, score]) => (
              <details className="metric-card" key={name}>
                <summary>{humaniseLabel(name)}</summary>
                <strong>{score.percentage.toFixed(2)}%</strong>
                <span>{score.status}</span>
                <p>
                  <code>{score.formula}</code>
                </p>
                <dl className="readable-details">
                  {Object.entries(score.details).map(([detail, value]) => (
                    <div key={detail}>
                      <dt>{humaniseLabel(detail)}</dt>
                      <dd>{value.toFixed(2)}%</dd>
                    </div>
                  ))}
                </dl>
              </details>
            ))}
          </div>

          <div className="download-grid">
            <DownloadCard
              title="Quality report"
              filename={result.report_filename}
              url={result.report_download_url}
            />
          </div>
        </section>
      ) : null}
    </div>
  );
}
