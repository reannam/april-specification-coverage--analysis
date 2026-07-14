import { useState } from "react";

import DownloadCard from "../components/common/DownloadCard";
import FileUpload from "../components/common/FileUpload";
import PageHeader from "../components/common/PageHeader";
import StatusPanel from "../components/common/StatusPanel";
import { useWorkflow } from "../context/WorkflowContext";
import { postFormData } from "../services/api";
import type { CoverageResponse } from "../types/workflow";
import { humaniseLabel } from "../utils/formatters";

const formatPercentage = (value?: number) => {
    if (value === undefined || value === null) {
        return "—";
    }

    return `${value.toFixed(2)}%`;
};

export default function CoveragePage() {
    const workflow = useWorkflow();

    const [requirementsFile, setRequirementsFile] =
        useState<File | null>(null);

    const [vplanFile, setVplanFile] =
        useState<File | null>(null);

    const [edgeCaseFile, setEdgeCaseFile] =
        useState<File | null>(null);

    const [weakWordsFile, setWeakWordsFile] =
        useState<File | null>(null);

    const [status, setStatus] = useState<
        "idle" | "processing" | "error"
    >("idle");

    const [error, setError] = useState("");

    const cached = workflow.agentResult;

    /*
     * Requirements may exist either as:
     * - a browser File object from the current session
     * - a cached backend path returned by /api/run-agents
     */
    const requirementsUpload =
        requirementsFile ??
        workflow.requirementsFile;

    const cachedRequirements =
        cached?.requirements_file ??
        null;

    /*
     * Prefer backend file paths, but fall back to download URLs
     * when a direct path was not included in the API response.
     */
    const cachedVplan =
        cached?.vplan_file ??
        cached?.vplan_download_url ??
        null;

    const cachedEdgeCases =
        cached?.edge_case_file ??
        cached?.edge_cases_download_url ??
        null;

    const cachedWeakWords =
        cached?.weak_words_file ??
        cached?.weak_words_download_url ??
        null;

    const hasRequirements = Boolean(
        requirementsUpload ||
        cachedRequirements
    );

    const hasManualCoverageFiles = Boolean(
        vplanFile &&
        edgeCaseFile &&
        weakWordsFile
    );

    const hasCachedCoverageFiles = Boolean(
        cachedVplan &&
        cachedEdgeCases &&
        cachedWeakWords
    );

    const canRun =
        hasRequirements &&
        (
            hasManualCoverageFiles ||
            hasCachedCoverageFiles
        );

    const runCoverage = async () => {
        if (!hasRequirements) {
            setStatus("error");
            setError(
                "Upload the requirements file before running coverage.",
            );
            return;
        }

        if (
            !hasManualCoverageFiles &&
            !hasCachedCoverageFiles
        ) {
            setStatus("error");
            setError(
                "Coverage requires a vPlan, edge-case report, and weak-language report.",
            );
            return;
        }

        setStatus("processing");
        setError("");

        try {
            const formData = new FormData();

            /*
             * Use the browser upload when available.
             * Otherwise send the cached backend path.
             */
            if (requirementsUpload) {
                formData.append(
                    "requirements_file",
                    requirementsUpload,
                );
            } else if (cachedRequirements) {
                formData.append(
                    "requirements_path",
                    cachedRequirements,
                );
            }

            /*
             * Use a complete manually uploaded coverage set when
             * all three files were selected.
             */
            if (
                vplanFile &&
                edgeCaseFile &&
                weakWordsFile
            ) {
                formData.append(
                    "vplan_upload",
                    vplanFile,
                );

                formData.append(
                    "edge_case_upload",
                    edgeCaseFile,
                );

                formData.append(
                    "weak_words_upload",
                    weakWordsFile,
                );
            } else {
                /*
                 * Otherwise reuse the latest generated outputs.
                 */
                formData.append(
                    "vplan_file",
                    cachedVplan as string,
                );

                formData.append(
                    "edge_case_file",
                    cachedEdgeCases as string,
                );

                formData.append(
                    "weak_words_file",
                    cachedWeakWords as string,
                );
            }

            const result =
                await postFormData<CoverageResponse>(
                    "/api/run-coverage",
                    formData,
                );

            workflow.setCoverageResult(result);
            setStatus("idle");
        } catch (requestError) {
            setStatus("error");

            setError(
                requestError instanceof Error
                    ? requestError.message
                    : "Coverage failed.",
            );
        }
    };

    const result = workflow.coverageResult;

    return (
        <div className="stack-lg">
            <PageHeader
                eyebrow="Verification"
                title="Coverage"
                description="Check requirement mapping, weighted coverage, traceability, testability, orphan items, gaps and ambiguity."
            />

            <section className="panel">
                <div className="section-heading">
                    <div>
                        <h2>Coverage inputs</h2>

                        <p>
                            Use the latest generated outputs or
                            upload all four files manually.
                        </p>
                    </div>

                    <span
                        className={`pill ${
                            hasCachedCoverageFiles &&
                            cachedRequirements
                                ? "success"
                                : ""
                        }`}
                    >
                        {hasCachedCoverageFiles &&
                        cachedRequirements
                            ? "Cached outputs available"
                            : "No complete cached output set"}
                    </span>
                </div>

                <div className="upload-grid">
                    <FileUpload
                        label="Requirements"
                        description={
                            cachedRequirements
                                ? "Cached requirements will be used"
                                : "Upload requirements"
                        }
                        file={requirementsUpload}
                        onChange={setRequirementsFile}
                        disabled={status === "processing"}
                    />

                    <FileUpload
                        label="vPlan"
                        description={
                            cachedVplan
                                ? "Cached vPlan will be used"
                                : "Upload vPlan"
                        }
                        file={vplanFile}
                        onChange={setVplanFile}
                        disabled={status === "processing"}
                    />

                    <FileUpload
                        label="Edge cases"
                        description={
                            cachedEdgeCases
                                ? "Cached edge cases will be used"
                                : "Upload edge cases"
                        }
                        file={edgeCaseFile}
                        onChange={setEdgeCaseFile}
                        disabled={status === "processing"}
                    />

                    <FileUpload
                        label="Weak language"
                        description={
                            cachedWeakWords
                                ? "Cached weak-language report will be used"
                                : "Upload weak-language report"
                        }
                        file={weakWordsFile}
                        onChange={setWeakWordsFile}
                        disabled={status === "processing"}
                    />
                </div>

                {status === "processing" && (
                    <StatusPanel
                        status="processing"
                        message="Running deterministic coverage checks and report generation."
                    />
                )}

                {status === "error" && (
                    <StatusPanel
                        status="error"
                        message={error}
                    />
                )}

                <button
                    className="button primary"
                    disabled={
                        !canRun ||
                        status === "processing"
                    }
                    onClick={runCoverage}
                    type="button"
                >
                    {status === "processing"
                        ? "Running coverage checks…"
                        : "Run coverage checks"}
                </button>
            </section>

            {result && (
                <>
                    <div className="metric-grid">
                        {Object.entries(
                            result.coverage_summary ?? {},
                        ).map(([key, value]) => (
                            <div
                                className="metric-card"
                                key={key}
                            >
                                <span>
                                    {humaniseLabel(key)}
                                </span>

                                <strong>
                                    {value ?? "—"}
                                </strong>
                            </div>
                        ))}
                    </div>

                    <div className="metric-grid">
                        {Object.entries(
                            result.coverage_percentages ??
                                {},
                        ).map(([key, value]) => (
                            <div
                                className="metric-card"
                                key={key}
                            >
                                <span>
                                    {humaniseLabel(key)}
                                </span>

                                <strong>
                                    {formatPercentage(value)}
                                </strong>
                            </div>
                        ))}
                    </div>

                    <section>
                        <h2>Coverage reports</h2>

                        <div className="download-grid">
                            {result.coverage_status_download_url && (
                                <DownloadCard
                                    title="Coverage status"
                                    filename={result.coverage_status_filename}
                                    url={result.coverage_status_download_url}
                                />
                            )}

                            {Object.entries(
                                result.coverage_output_files ??
                                    {},
                            ).map(([key, file]) => (
                                <DownloadCard
                                    key={key}
                                    title={humaniseLabel(key)}
                                    filename={file.filename}
                                    url={file.download_url}
                                />
                            ))}
                        </div>
                    </section>
                </>
            )}
        </div>
    );
}