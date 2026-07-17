import { useState } from "react";

import DownloadCard from "../components/common/DownloadCard";
import FileUpload from "../components/common/FileUpload";
import PageHeader from "../components/common/PageHeader";
import ReadableRecords from "../components/common/ReadableRecords";
import StatusPanel from "../components/common/StatusPanel";
import { postFormData } from "../services/api";
import type {
  ComparisonResponse,
} from "../types/workflow";
import { humaniseLabel } from "../utils/formatters";

type RunStatus = "idle" | "processing" | "error";

export default function InconsistenciesPage() {
  const [oldSpecification, setOldSpecification] = useState<File | null>(null);
  const [newSpecification, setNewSpecification] = useState<File | null>(null);
  const [comparisonStatus, setComparisonStatus] = useState<RunStatus>("idle");
  const [comparisonError, setComparisonError] = useState("");
  const [comparisonResult, setComparisonResult] =
    useState<ComparisonResponse | null>(null);

  const compareSpecifications = async () => {
    if (!oldSpecification || !newSpecification) return;
    setComparisonStatus("processing");
    setComparisonError("");

    try {
      const formData = new FormData();
      formData.append("old_specification", oldSpecification);
      formData.append("new_specification", newSpecification);
      const result = await postFormData<ComparisonResponse>(
        "/api/compare-specifications",
        formData,
      );
      setComparisonResult(result);
      setComparisonStatus("idle");
    } catch (error) {
      setComparisonStatus("error");
      setComparisonError(
        error instanceof Error ? error.message : "Specification comparison failed.",
      );
    }
  };

  const comparison = comparisonResult?.comparison;

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Analyse and compare"
        title="Compare specification versions"
        description="Compare two extracted specification versions and inspect their structural and engineering-content changes."
      />

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Compare specification versions</h2>
            <p>Upload the older and newer extractor JSON documents.</p>
          </div>
        </div>

        <div className="upload-grid">
          <FileUpload
            label="Older specification"
            description="Upload the earlier document.json"
            file={oldSpecification}
            onChange={setOldSpecification}
            disabled={comparisonStatus === "processing"}
          />
          <FileUpload
            label="Newer specification"
            description="Upload the later document.json"
            file={newSpecification}
            onChange={setNewSpecification}
            disabled={comparisonStatus === "processing"}
          />
        </div>

        <button
          className="button primary"
          disabled={!oldSpecification || !newSpecification || comparisonStatus === "processing"}
          onClick={compareSpecifications}
        >
          Compare versions
        </button>

        {comparisonStatus === "processing" ? (
          <StatusPanel status="processing" message="Comparing document structure and engineering content…" />
        ) : null}
        {comparisonStatus === "error" ? (
          <StatusPanel status="error" message={comparisonError} />
        ) : null}
      </section>

      {comparison ? (
        <>
          <div className="metric-grid">
            <div className="metric-card">
              <span>Total changes</span>
              <strong>{comparison.summary.total_changes}</strong>
            </div>
            {Object.entries(comparison.summary.by_change_type).map(([label, count]) => (
              <div className="metric-card" key={label}>
                <span>{humaniseLabel(label)}</span>
                <strong>{count}</strong>
              </div>
            ))}
          </div>

          <section className="report-section">
            <h2>Comparison downloads</h2>
            <div className="download-grid">
              {Object.entries(comparisonResult.output_files).map(([name, file]) => (
                <DownloadCard
                  key={name}
                  title={humaniseLabel(name)}
                  filename={file.filename}
                  url={file.download_url}
                />
              ))}
            </div>
          </section>

          <section className="results-browser">
            <div className="results-browser-toolbar">
              <div>
                <strong>Changes by review area</strong>
                <span>{comparison.summary.total_changes} changes</span>
              </div>
            </div>
            <div className="section-accordion-list">
              {Object.entries(comparison.organized_changes).map(([section, categories]) => {
                const sectionCount = Object.values(categories).reduce(
                  (total, records) => total + records.length,
                  0,
                );
                return (
                  <details className="section-accordion" key={section} open={sectionCount > 0}>
                    <summary>
                      <span>{section}</span>
                      <small>{sectionCount} changes</small>
                    </summary>
                    {Object.entries(categories).map(([category, records]) => (
                      <details className="section-accordion" key={category}>
                        <summary>
                          <span>{category}</span>
                          <small>{records.length}</small>
                        </summary>
                        <ReadableRecords
                          records={records}
                          idKeys={["identifier", "area", "change_type"]}
                          empty="No changes in this category."
                        />
                      </details>
                    ))}
                  </details>
                );
              })}
            </div>
          </section>
        </>
      ) : null}

    </div>
  );
}
