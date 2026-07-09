import { useRef, useState } from "react";
import "./App.css";

import ChapterExtractionFlow from "./ChapterExtractionFlow.tsx";

type ProcessingStatus = "idle" | "ready" | "processing" | "success" | "error";
type CoverageStatus = "idle" | "processing" | "success" | "error";
type ActiveTab = "analysis" | "metrics" | "coverage" | "chapter-extractor";

type AgentUsage = {
    agent_name: string;
    model_name?: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    total_cost: string;
};

type GeneratedOutputCache = {
    requirements_filename?: string | null;

    vplan_file?: string | null;
    edge_case_file?: string | null;
    weak_words_file?: string | null;

    vplan_download_url?: string | null;
    edge_cases_download_url?: string | null;
    weak_words_download_url?: string | null;

    vplan_filename?: string | null;
    edge_cases_filename?: string | null;
    weak_words_filename?: string | null;
};

type AgentResponse = {
    message?: string;

    vplan_download_url: string;
    edge_cases_download_url: string;

    vplan_filename?: string;
    edge_cases_filename?: string;

    vplan_file?: string | null;
    edge_case_file?: string | null;
    weak_words_file?: string | null;

    weak_words_download_url?: string | null;
    weak_words_filename?: string | null;

    langsmith_log_download_url?: string | null;
    langsmith_log_filename?: string | null;

    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
    estimated_cost_usd?: string;

    agent_usage?: AgentUsage[];

    usage_chart_urls?: Record<string, string>;
    usage_csv_urls?: Record<string, string>;

    blocked_test_report_download_url?: string | null;
    blocked_test_report_filename?: string | null;

    requirement_test_links_download_url?: string | null;
    requirement_test_links_filename?: string | null;
};

type CoverageSummary = {
    total_spec_items?: number;
    covered?: number;
    partially_covered?: number;
    uncovered?: number;
    ambiguity_blocked?: number;
    orphan_vplan_items?: number;
};

type CoveragePercentages = {
    requirement_mapping_coverage?: number;
    weighted_coverage?: number;
    traceability_coverage?: number;
    testability_coverage?: number;
    orphan_rate?: number;
};

type CoverageOutputFile = {
    filename?: string | null;
    download_url?: string | null;
};

type CoverageResponse = {
    message?: string;

    vplan_download_url?: string | null;
    vplan_filename?: string | null;

    edge_cases_download_url?: string | null;
    edge_cases_filename?: string | null;

    weak_words_download_url?: string | null;
    weak_words_filename?: string | null;

    coverage_status_download_url?: string | null;
    coverage_status_filename?: string | null;

    coverage_summary?: CoverageSummary;
    coverage_percentages?: CoveragePercentages;

    coverage_output_files?: Record<string, CoverageOutputFile>;

    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
    estimated_cost_usd?: string | number | null;

    coverage_usage?: Record<string, unknown>;
    usage_report_files?: Record<string, CoverageOutputFile>;
};

const API_BASE_URL = "http://localhost:8000";

const GENERATED_OUTPUT_CACHE_KEY = "spec_ai_generated_output_cache";

const loadGeneratedOutputCache = (): GeneratedOutputCache | null => {
    try {
        const rawCache = window.localStorage.getItem(GENERATED_OUTPUT_CACHE_KEY);
        return rawCache ? JSON.parse(rawCache) : null;
    } catch {
        return null;
    }
};

const saveGeneratedOutputCache = (cache: GeneratedOutputCache | null) => {
    if (!cache) {
        window.localStorage.removeItem(GENERATED_OUTPUT_CACHE_KEY);
        return;
    }

    window.localStorage.setItem(GENERATED_OUTPUT_CACHE_KEY, JSON.stringify(cache));
};

function App() {
    const [activeTab, setActiveTab] = useState<ActiveTab>("analysis");
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    const [status, setStatus] = useState<ProcessingStatus>("idle");
    const [coverageStatus, setCoverageStatus] = useState<CoverageStatus>("idle");

    const [errorMessage, setErrorMessage] = useState<string>("");
    const [coverageErrorMessage, setCoverageErrorMessage] = useState<string>("");

    const [result, setResult] = useState<AgentResponse | null>(null);
    const [coverageResult, setCoverageResult] = useState<CoverageResponse | null>(null);

    const [progress, setProgress] = useState<number>(0);
    const [coverageProgress, setCoverageProgress] = useState<number>(0);

    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const progressIntervalRef = useRef<number | null>(null);
    const coverageProgressIntervalRef = useRef<number | null>(null);

    const [manualRequirementsFile, setManualRequirementsFile] = useState<File | null>(null);
    const [manualVplanFile, setManualVplanFile] = useState<File | null>(null);
    const [manualEdgeCaseFile, setManualEdgeCaseFile] = useState<File | null>(null);
    const [manualWeakWordsFile, setManualWeakWordsFile] = useState<File | null>(null);

    const [generatedOutputCache, setGeneratedOutputCache] = useState<GeneratedOutputCache | null>(
        () => loadGeneratedOutputCache()
    );

    const startFakeProgress = () => {
        setProgress(6);

        progressIntervalRef.current = window.setInterval(() => {
            setProgress((current) => {
                if (current >= 92) return current;
                return current + Math.floor(Math.random() * 7) + 2;
            });
        }, 650);
    };

    const stopFakeProgress = () => {
        if (progressIntervalRef.current !== null) {
            window.clearInterval(progressIntervalRef.current);
            progressIntervalRef.current = null;
        }
    };

    const startCoverageProgress = () => {
        setCoverageProgress(6);

        coverageProgressIntervalRef.current = window.setInterval(() => {
            setCoverageProgress((current) => {
                if (current >= 92) return current;
                return current + Math.floor(Math.random() * 6) + 2;
            });
        }, 700);
    };

    const stopCoverageProgress = () => {
        if (coverageProgressIntervalRef.current !== null) {
            window.clearInterval(coverageProgressIntervalRef.current);
            coverageProgressIntervalRef.current = null;
        }
    };

    const resetState = () => {
        stopFakeProgress();
        stopCoverageProgress();

        setSelectedFile(null);
        setStatus("idle");
        setCoverageStatus("idle");

        setErrorMessage("");
        setCoverageErrorMessage("");

        setResult(null);
        setCoverageResult(null);

        setProgress(0);
        setCoverageProgress(0);
        setActiveTab("analysis");

        setGeneratedOutputCache(null);
        saveGeneratedOutputCache(null);

        setManualVplanFile(null);
        setManualEdgeCaseFile(null);
        setManualWeakWordsFile(null);
        setManualRequirementsFile(null);

        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    const isJsonUpload = (file: File | null) => {
        if (!file) return false;
        return file.type === "application/json" || file.name.toLowerCase().endsWith(".json");
    };

    const handleCoverageInputFileChange = (
        file: File | undefined,
        setter: React.Dispatch<React.SetStateAction<File | null>>,
        label: string
    ) => {
        setCoverageErrorMessage("");

        if (!file) {
            setter(null);
            return;
        }

        if (!isJsonUpload(file)) {
            setter(null);
            setCoverageStatus("error");
            setCoverageErrorMessage(`${label} must be a valid JSON file.`);
            return;
        }

        setter(file);
    };

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];

        setErrorMessage("");
        setCoverageErrorMessage("");

        setResult(null);
        setCoverageResult(null);

        setGeneratedOutputCache(null);
        saveGeneratedOutputCache(null);

        setManualVplanFile(null);
        setManualEdgeCaseFile(null);
        setManualWeakWordsFile(null);
        setManualRequirementsFile(null);

        setProgress(0);
        setCoverageProgress(0);
        setCoverageStatus("idle");

        if (!file) {
            setSelectedFile(null);
            setStatus("idle");
            return;
        }

        const isJsonFile =
            file.type === "application/json" || file.name.toLowerCase().endsWith(".json");

        if (!isJsonFile) {
            setSelectedFile(null);
            setStatus("error");
            setErrorMessage("Please upload a valid JSON requirements file.");
            return;
        }

        setSelectedFile(file);
        setStatus("ready");
    };

    const handleGenerate = async () => {
        if (!selectedFile) {
            setStatus("error");
            setErrorMessage("Please upload a requirements file first.");
            return;
        }

        setStatus("processing");
        setCoverageStatus("idle");

        setErrorMessage("");
        setCoverageErrorMessage("");

        setResult(null);
        setCoverageResult(null);

        setActiveTab("analysis");
        startFakeProgress();

        try {
            const formData = new FormData();
            formData.append("requirements_file", selectedFile);

            const response = await fetch(`${API_BASE_URL}/api/run-agents`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || "The backend failed to process the file.");
            }

            const data: AgentResponse = await response.json();

            const nextCache: GeneratedOutputCache = {
                requirements_filename: selectedFile.name,

                vplan_file: data.vplan_file ?? null,
                edge_case_file: data.edge_case_file ?? null,
                weak_words_file: data.weak_words_file ?? null,

                vplan_download_url: data.vplan_download_url ?? null,
                edge_cases_download_url: data.edge_cases_download_url ?? null,
                weak_words_download_url: data.weak_words_download_url ?? null,

                vplan_filename: data.vplan_filename ?? null,
                edge_cases_filename: data.edge_cases_filename ?? null,
                weak_words_filename: data.weak_words_filename ?? null,
            };

            setGeneratedOutputCache(nextCache);
            saveGeneratedOutputCache(nextCache);

            stopFakeProgress();
            setProgress(100);
            setResult(data);
            setStatus("success");
        } catch (error) {
            stopFakeProgress();
            setProgress(0);
            setStatus("error");
            setErrorMessage(error instanceof Error ? error.message : "An unknown error occurred.");
        }
    };

    const handleRunCoverage = async () => {
        const requirementsForCoverage = manualRequirementsFile ?? selectedFile;

        if (!requirementsForCoverage) {
            setCoverageStatus("error");
            setCoverageErrorMessage("Please upload a requirements file first.");
            return;
        }

        const hasManualCoverageFiles =
            manualVplanFile && manualEdgeCaseFile && manualWeakWordsFile;

        const vplanFile =
            generatedOutputCache?.vplan_file ?? generatedOutputCache?.vplan_download_url;

        const edgeCaseFile =
            generatedOutputCache?.edge_case_file ?? generatedOutputCache?.edge_cases_download_url;

        const weakWordsFile =
            generatedOutputCache?.weak_words_file ?? generatedOutputCache?.weak_words_download_url;

        const hasCachedCoverageFiles = Boolean(vplanFile && edgeCaseFile && weakWordsFile);

        if (!hasManualCoverageFiles && !hasCachedCoverageFiles) {
            setCoverageStatus("error");
            setCoverageErrorMessage(
                "Coverage needs a vPlan file, edge-case file, and weak-words file. Run generation first or upload all three files manually."
            );
            return;
        }

        setCoverageStatus("processing");
        setCoverageErrorMessage("");
        setCoverageResult(null);
        setActiveTab("coverage");
        startCoverageProgress();

        try {
            const formData = new FormData();

            formData.append("requirements_file", requirementsForCoverage);

            if (hasManualCoverageFiles) {
                formData.append("vplan_upload", manualVplanFile);
                formData.append("edge_case_upload", manualEdgeCaseFile);
                formData.append("weak_words_upload", manualWeakWordsFile);
            } else {
                formData.append("vplan_file", vplanFile as string);
                formData.append("edge_case_file", edgeCaseFile as string);
                formData.append("weak_words_file", weakWordsFile as string);
            }

            const response = await fetch(`${API_BASE_URL}/api/run-coverage`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || "The backend failed to run coverage checks.");
            }

            const data: CoverageResponse = await response.json();

            stopCoverageProgress();
            setCoverageProgress(100);
            setCoverageResult(data);
            setCoverageStatus("success");
        } catch (error) {
            stopCoverageProgress();
            setCoverageProgress(0);
            setCoverageStatus("error");
            setCoverageErrorMessage(
                error instanceof Error ? error.message : "An unknown coverage error occurred."
            );
        }
    };

    const getDownloadUrl = (url?: string | null) => {
        if (!url) return "#";

        if (url.startsWith("http")) return url;

        let normalisedUrl = url.trim();

        normalisedUrl = normalisedUrl.replace(/^\.\/+/, "/");
        normalisedUrl = normalisedUrl.replace(/^backend\/outputs/i, "/outputs");
        normalisedUrl = normalisedUrl.replace(/^\/backend\/outputs/i, "/outputs");

        if (!normalisedUrl.startsWith("/")) {
            normalisedUrl = `/${normalisedUrl}`;
        }

        return `${API_BASE_URL}${normalisedUrl}`;
    };

    const formatNumber = (value?: number) => {
        if (value === undefined || value === null) return "Not available";
        return value.toLocaleString();
    };

    const formatCost = (value?: string | number | null) => {
        if (value === undefined || value === null || value === "") return "Not available";
        return typeof value === "number" ? `$${value.toFixed(4)}` : value;
    };

    const formatPercentage = (value?: number) => {
        if (value === undefined || value === null) return "Not available";
        return `${value.toFixed(2)}%`;
    };

    const fileSize = selectedFile ? `${(selectedFile.size / 1024).toFixed(1)} KB` : null;

    return (
        <main className="page">
            <section className="shell">
                <section className="heroPanel">
                    <div>
                        <p className="eyebrow">Specification Coverage Analysis</p>
                        <h1>Generate verification outputs from requirements.</h1>
                        <p className="description">
                            Upload a structured requirements JSON file, run the agent workflow, and download
                            the generated vPlan, edge-case, and coverage analysis files.
                        </p>
                    </div>

                    <div className="stepsCard">
                        <p className="stepsTitle">Workflow</p>

                        <div className="stepItem">
                            <span className="stepNumber">1</span>
                            <div>
                                <strong>Upload requirements</strong>
                                <p>Provide the JSON requirements file.</p>
                            </div>
                        </div>

                        <div className="stepItem">
                            <span className="stepNumber">2</span>
                            <div>
                                <strong>Run agents</strong>
                                <p>Generate the vPlan and edge-case outputs.</p>
                            </div>
                        </div>

                        <div className="stepItem">
                            <span className="stepNumber">3</span>
                            <div>
                                <strong>Run coverage</strong>
                                <p>Check mapping, traceability, testability, gaps, and ambiguity.</p>
                            </div>
                        </div>
                    </div>
                </section>

                <section className="mainPanel">
                    <div className="tabs">
                        <button
                            className={`tabButton ${activeTab === "analysis" ? "active" : ""}`}
                            onClick={() => setActiveTab("analysis")}
                            type="button"
                        >
                            Generate Verification Plan
                        </button>

                        <button
                            className={`tabButton ${activeTab === "metrics" ? "active" : ""}`}
                            onClick={() => setActiveTab("metrics")}
                            type="button"
                        >
                            Run Metrics
                        </button>

                        <button
                            className={`tabButton ${activeTab === "coverage" ? "active" : ""}`}
                            onClick={() => setActiveTab("coverage")}
                            type="button"
                        >
                            Coverage
                        </button>
                        <button
                            className={`tabButton ${activeTab === "chapter-extractor" ? "active" : ""}`}
                            onClick={() => setActiveTab("chapter-extractor")}
                            type="button"
                        >
                            Chapter Extractor
                        </button>
                    </div>

                    {activeTab === "analysis" && (
                        <>
                            <div className="panelHeader">
                                <div>
                                    <h2>Requirements upload</h2>
                                    <p>Select a JSON file to begin.</p>
                                </div>

                                <span className={`statusPill status-${status}`}>
                                    {status === "idle" && "Waiting"}
                                    {status === "ready" && "Ready"}
                                    {status === "processing" && "Processing"}
                                    {status === "success" && "Complete"}
                                    {status === "error" && "Error"}
                                </span>
                            </div>

                            <div className="uploadBox">
                                <input
                                    ref={fileInputRef}
                                    id="requirements-file"
                                    type="file"
                                    accept=".json,application/json"
                                    onChange={handleFileChange}
                                    disabled={status === "processing" || coverageStatus === "processing"}
                                />

                                <label htmlFor="requirements-file" className="uploadLabel">
                                    <span className="uploadIcon">↑</span>

                                    <span className="uploadText">
                                        <strong>
                                            {selectedFile ? selectedFile.name : "Choose requirements JSON"}
                                        </strong>
                                        <small>
                                            {selectedFile
                                                ? `${fileSize} selected`
                                                : "Click to browse for a requirements file."}
                                        </small>
                                    </span>

                                    <span className="browseButton">Browse</span>
                                </label>
                            </div>

                            {status === "processing" && (
                                <div className="processingPanel">
                                    <div className="processingTop">
                                        <div className="spinner" />
                                        <div>
                                            <strong>Processing requirements</strong>
                                            <p>Running vPlan generation and edge-case extraction.</p>
                                        </div>
                                    </div>

                                    <div className="progressOuter" aria-label="Processing progress">
                                        <div className="progressInner" style={{ width: `${progress}%` }} />
                                    </div>

                                    <div className="progressMeta">
                                        <span>Agent workflow in progress</span>
                                        <span>{progress}%</span>
                                    </div>
                                </div>
                            )}

                            {status === "error" && (
                                <div className="alert error">
                                    <strong>Something went wrong</strong>
                                    <p>{errorMessage}</p>
                                </div>
                            )}

                            {status === "success" && result && (
                                <div className="resultPanel">
                                    <div className="alert success">
                                        <strong>Generation complete</strong>
                                        <p>Your output files are ready.</p>
                                    </div>

                                    <div className="resultGrid">
                                        <a
                                            className="resultCard"
                                            href={getDownloadUrl(result.vplan_download_url)}
                                            download={result.vplan_filename ?? "generated_vplan.json"}
                                        >
                                            <span className="resultIcon">JSON</span>
                                            <span>
                                                <strong>vPlan file</strong>
                                                <small>{result.vplan_filename ?? "generated_vplan.json"}</small>
                                            </span>
                                        </a>

                                        <a
                                            className="resultCard"
                                            href={getDownloadUrl(result.edge_cases_download_url)}
                                            download={result.edge_cases_filename ?? "generated_edge_cases.json"}
                                        >
                                            <span className="resultIcon">JSON</span>
                                            <span>
                                                <strong>Edge-case file</strong>
                                                <small>
                                                    {result.edge_cases_filename ?? "generated_edge_cases.json"}
                                                </small>
                                            </span>
                                        </a>

                                        {result.requirement_test_links_download_url && (
                                            <a
                                                className="resultCard"
                                                href={getDownloadUrl(result.requirement_test_links_download_url)}
                                                download={
                                                    result.requirement_test_links_filename ??
                                                    "requirement_test_links.csv"
                                                }
                                            >
                                                <span className="resultIcon">CSV</span>
                                                <span>
                                                    <strong>Requirement-test links</strong>
                                                    <small>
                                                        {result.requirement_test_links_filename ??
                                                            "requirement_test_links.csv"}
                                                    </small>
                                                </span>
                                            </a>
                                        )}

                                        {result.blocked_test_report_download_url && (
                                            <a
                                                className="resultCard"
                                                href={getDownloadUrl(result.blocked_test_report_download_url)}
                                                download={
                                                    result.blocked_test_report_filename ??
                                                    "blocked_test_report.json"
                                                }
                                            >
                                                <span className="resultIcon">JSON</span>
                                                <span>
                                                    <strong>Blocked / partial report</strong>
                                                    <small>
                                                        {result.blocked_test_report_filename ??
                                                            "blocked_test_report.json"}
                                                    </small>
                                                </span>
                                            </a>
                                        )}
                                    </div>

                                    <div className="coveragePrompt">
                                        <div>
                                            <strong>Run coverage checks?</strong>
                                            <p>
                                                Analyse requirement mapping, weighted coverage, traceability,
                                                testability, orphan vPlan items, gaps, and ambiguity.
                                            </p>
                                        </div>

                                        <button
                                            className="primaryButton"
                                            onClick={handleRunCoverage}
                                            disabled={coverageStatus === "processing"}
                                            type="button"
                                        >
                                            {coverageStatus === "processing"
                                                ? "Running coverage..."
                                                : "Run coverage checks"}
                                        </button>
                                    </div>
                                </div>
                            )}

                            <div className="actions">
                                <button
                                    className="primaryButton"
                                    onClick={handleGenerate}
                                    disabled={!selectedFile || status === "processing" || coverageStatus === "processing"}
                                    type="button"
                                >
                                    {status === "processing" ? "Generating..." : "Generate outputs"}
                                </button>

                                <button
                                    className="ghostButton"
                                    onClick={resetState}
                                    disabled={status === "processing" || coverageStatus === "processing"}
                                    type="button"
                                >
                                    Reset
                                </button>
                            </div>
                        </>
                    )}

                    {activeTab === "metrics" && (
                        <section className="metricsPanel">
                            <div className="panelHeader">
                                <div>
                                    <h2>Run metrics</h2>
                                    <p>Token usage and estimated cost for the latest completed run.</p>
                                </div>

                                <span className={`statusPill status-${result ? "success" : "idle"}`}>
                                    {result ? "Available" : "No run"}
                                </span>
                            </div>

                            {!result && (
                                <div className="emptyState">
                                    <strong>No run completed yet</strong>
                                    <p>Run the analysis first, then metrics for the latest run will appear here.</p>
                                </div>
                            )}

                            {result && (
                                <>
                                    <div className="metricsGrid">
                                        <div className="metricCard">
                                            <span>Total tokens</span>
                                            <strong>{formatNumber(result.total_tokens)}</strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Input tokens</span>
                                            <strong>{formatNumber(result.input_tokens)}</strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Output tokens</span>
                                            <strong>{formatNumber(result.output_tokens)}</strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Estimated cost</span>
                                            <strong>{formatCost(result.estimated_cost_usd)}</strong>
                                        </div>
                                    </div>

                                    {result.langsmith_log_download_url ? (
                                        <a
                                            className="resultCard"
                                            href={getDownloadUrl(result.langsmith_log_download_url)}
                                            download={result.langsmith_log_filename ?? "langsmith_run_log.json"}
                                        >
                                            <span className="resultIcon">JSON</span>
                                            <span>
                                                <strong>Usage log</strong>
                                                <small>
                                                    {result.langsmith_log_filename ??
                                                        "Download token and cost log"}
                                                </small>
                                            </span>
                                        </a>
                                    ) : (
                                        <div className="emptyState">
                                            <strong>LangSmith log not connected yet</strong>
                                            <p>
                                                The metrics tab is ready, but the backend response does not currently
                                                include token or cost information.
                                            </p>
                                        </div>
                                    )}

                                    {result.usage_chart_urls && Object.keys(result.usage_chart_urls).length > 0 && (
                                        <section className="chartSection">
                                            <div className="sectionHeader">
                                                <p className="eyebrow">Usage charts</p>
                                                <h2>Run analytics</h2>
                                            </div>

                                            <div className="chartGrid">
                                                {Object.entries(result.usage_chart_urls).map(
                                                    ([chartName, chartUrl]) => (
                                                        <article className="chartCard" key={chartName}>
                                                            <h3>{chartName.replaceAll("_", " ")}</h3>
                                                            <img
                                                                src={getDownloadUrl(chartUrl)}
                                                                alt={chartName.replaceAll("_", " ")}
                                                            />
                                                        </article>
                                                    )
                                                )}
                                            </div>
                                        </section>
                                    )}
                                </>
                            )}
                        </section>
                    )}

                    {activeTab === "coverage" && (
                        <section className="metricsPanel">
                            <div className="panelHeader">
                                <div>
                                    <h2>Coverage checks</h2>
                                    <p>Spec-to-vPlan coverage, gaps, ambiguity, and traceability results.</p>
                                </div>

                                <span className={`statusPill status-${coverageStatus}`}>
                                    {coverageStatus === "idle" && "Not run"}
                                    {coverageStatus === "processing" && "Processing"}
                                    {coverageStatus === "success" && "Complete"}
                                    {coverageStatus === "error" && "Error"}
                                </span>
                            </div>

                            <section className="coverageInputPanel">
                                <div className="coverageInputHeader">
                                    <div>
                                        <p className="eyebrow">Coverage inputs</p>
                                        <h3>Upload coverage files or use cached outputs</h3>
                                        <p>
                                            Coverage requires four files: requirements, vPlan, edge cases,
                                            and weak-word analysis.
                                        </p>
                                    </div>

                                    <span className={`statusPill status-${generatedOutputCache ? "success" : "idle"}`}>
                                        {generatedOutputCache ? "Cached outputs available" : "No cached outputs"}
                                    </span>
                                </div>

                                <div className="coverageUploadGrid coverageUploadGridTwoByTwo">
                                    <label className={`coverageUploadCard ${manualRequirementsFile || selectedFile ? "hasFile" : ""}`}>
                                        <input
                                            type="file"
                                            accept=".json,application/json"
                                            disabled={coverageStatus === "processing"}
                                            onChange={(event) =>
                                                handleCoverageInputFileChange(
                                                    event.target.files?.[0],
                                                    setManualRequirementsFile,
                                                    "Requirements file"
                                                )
                                            }
                                        />

                                        <span className="coverageUploadIcon">JSON</span>

                                        <span className="coverageUploadText">
                                            <strong>Requirements file</strong>
                                            <small>
                                                {manualRequirementsFile
                                                    ? manualRequirementsFile.name
                                                    : selectedFile
                                                        ? `${selectedFile.name} from analysis upload`
                                                        : "Upload requirements JSON"}
                                            </small>
                                        </span>
                                    </label>

                                    <label className={`coverageUploadCard ${manualVplanFile ? "hasFile" : ""}`}>
                                        <input
                                            type="file"
                                            accept=".json,application/json"
                                            disabled={coverageStatus === "processing"}
                                            onChange={(event) =>
                                                handleCoverageInputFileChange(
                                                    event.target.files?.[0],
                                                    setManualVplanFile,
                                                    "vPlan file"
                                                )
                                            }
                                        />

                                        <span className="coverageUploadIcon">JSON</span>

                                        <span className="coverageUploadText">
                                            <strong>vPlan file</strong>
                                            <small>
                                                {manualVplanFile
                                                    ? manualVplanFile.name
                                                    : generatedOutputCache
                                                        ? "Using cached vPlan if no upload selected"
                                                        : "Upload vPlan JSON"}
                                            </small>
                                        </span>
                                    </label>

                                    <label className={`coverageUploadCard ${manualEdgeCaseFile ? "hasFile" : ""}`}>
                                        <input
                                            type="file"
                                            accept=".json,application/json"
                                            disabled={coverageStatus === "processing"}
                                            onChange={(event) =>
                                                handleCoverageInputFileChange(
                                                    event.target.files?.[0],
                                                    setManualEdgeCaseFile,
                                                    "Edge-case file"
                                                )
                                            }
                                        />

                                        <span className="coverageUploadIcon">JSON</span>

                                        <span className="coverageUploadText">
                                            <strong>Edge-case file</strong>
                                            <small>
                                                {manualEdgeCaseFile
                                                    ? manualEdgeCaseFile.name
                                                    : generatedOutputCache
                                                        ? "Using cached edge cases if no upload selected"
                                                        : "Upload edge-case JSON"}
                                            </small>
                                        </span>
                                    </label>

                                    <label className={`coverageUploadCard ${manualWeakWordsFile ? "hasFile" : ""}`}>
                                        <input
                                            type="file"
                                            accept=".json,application/json"
                                            disabled={coverageStatus === "processing"}
                                            onChange={(event) =>
                                                handleCoverageInputFileChange(
                                                    event.target.files?.[0],
                                                    setManualWeakWordsFile,
                                                    "Weak-words file"
                                                )
                                            }
                                        />

                                        <span className="coverageUploadIcon">JSON</span>

                                        <span className="coverageUploadText">
                                            <strong>Weak-words file</strong>
                                            <small>
                                                {manualWeakWordsFile
                                                    ? manualWeakWordsFile.name
                                                    : generatedOutputCache
                                                        ? "Using cached weak words if no upload selected"
                                                        : "Upload weak-words JSON"}
                                            </small>
                                        </span>
                                    </label>
                                </div>

                                <div className="coverageInputActions">
                                    <button
                                        className="primaryButton"
                                        onClick={handleRunCoverage}
                                        disabled={
                                            coverageStatus === "processing" ||
                                            !(manualRequirementsFile || selectedFile) ||
                                            !(
                                                generatedOutputCache ||
                                                (manualVplanFile && manualEdgeCaseFile && manualWeakWordsFile)
                                            )
                                        }
                                        type="button"
                                    >
                                        {coverageStatus === "processing" ? "Running coverage..." : "Run coverage checks"}
                                    </button>

                                    {(manualRequirementsFile ||
                                        manualVplanFile ||
                                        manualEdgeCaseFile ||
                                        manualWeakWordsFile) && (
                                            <button
                                                className="ghostButton"
                                                type="button"
                                                disabled={coverageStatus === "processing"}
                                                onClick={() => {
                                                    setManualRequirementsFile(null);
                                                    setManualVplanFile(null);
                                                    setManualEdgeCaseFile(null);
                                                    setManualWeakWordsFile(null);
                                                }}
                                            >
                                                Clear uploaded files
                                            </button>
                                        )}
                                </div>
                            </section>

                            {coverageStatus === "idle" && (
                                <div className="emptyState">
                                    <strong>No coverage run yet</strong>
                                    <p>
                                        Upload the four coverage input files, or run generation first and use the cached outputs.
                                    </p>
                                </div>
                            )}

                            {coverageStatus === "processing" && (
                                <div className="processingPanel">
                                    <div className="processingTop">
                                        <div className="spinner" />
                                        <div>
                                            <strong>Running coverage checks</strong>
                                            <p>
                                                Calculating mapping, weighted coverage, traceability, testability,
                                                orphan rate, gaps, and ambiguity.
                                            </p>
                                        </div>
                                    </div>

                                    <div className="progressOuter" aria-label="Coverage progress">
                                        <div className="progressInner" style={{ width: `${coverageProgress}%` }} />
                                    </div>

                                    <div className="progressMeta">
                                        <span>Coverage workflow in progress</span>
                                        <span>{coverageProgress}%</span>
                                    </div>
                                </div>
                            )}

                            {coverageStatus === "error" && (
                                <div className="alert error">
                                    <strong>Coverage checks failed</strong>
                                    <p>{coverageErrorMessage}</p>
                                </div>
                            )}

                            {coverageStatus === "success" && coverageResult && (
                                <>
                                    <div className="alert success">
                                        <strong>Coverage checks complete</strong>
                                        <p>Your coverage summary and JSON reports are ready.</p>
                                    </div>

                                    <div className="metricsGrid">
                                        <div className="metricCard">
                                            <span>Total spec items</span>
                                            <strong>{formatNumber(coverageResult.coverage_summary?.total_spec_items)}</strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Covered</span>
                                            <strong>{formatNumber(coverageResult.coverage_summary?.covered)}</strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Partially covered</span>
                                            <strong>{formatNumber(coverageResult.coverage_summary?.partially_covered)}</strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Uncovered</span>
                                            <strong>{formatNumber(coverageResult.coverage_summary?.uncovered)}</strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Ambiguity-blocked</span>
                                            <strong>{formatNumber(coverageResult.coverage_summary?.ambiguity_blocked)}</strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Orphan vPlan items</span>
                                            <strong>{formatNumber(coverageResult.coverage_summary?.orphan_vplan_items)}</strong>
                                        </div>
                                    </div>

                                    <div className="metricsGrid">
                                        <div className="metricCard">
                                            <span>Requirement mapping</span>
                                            <strong>
                                                {formatPercentage(
                                                    coverageResult.coverage_percentages?.requirement_mapping_coverage
                                                )}
                                            </strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Weighted coverage</span>
                                            <strong>
                                                {formatPercentage(coverageResult.coverage_percentages?.weighted_coverage)}
                                            </strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Traceability</span>
                                            <strong>
                                                {formatPercentage(
                                                    coverageResult.coverage_percentages?.traceability_coverage
                                                )}
                                            </strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Testability</span>
                                            <strong>
                                                {formatPercentage(
                                                    coverageResult.coverage_percentages?.testability_coverage
                                                )}
                                            </strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Orphan rate</span>
                                            <strong>{formatPercentage(coverageResult.coverage_percentages?.orphan_rate)}</strong>
                                        </div>

                                        <div className="metricCard">
                                            <span>Coverage cost</span>
                                            <strong>{formatCost(coverageResult.estimated_cost_usd)}</strong>
                                        </div>
                                    </div>

                                    {coverageResult.coverage_output_files && (
                                        <div className="resultGrid">
                                            {Object.entries(coverageResult.coverage_output_files).map(
                                                ([key, file]) =>
                                                    file.download_url && (
                                                        <a
                                                            className="resultCard"
                                                            href={getDownloadUrl(file.download_url)}
                                                            download={file.filename ?? `${key}.json`}
                                                            key={key}
                                                        >
                                                            <span className="resultIcon">JSON</span>
                                                            <span>
                                                                <strong>
                                                                    {key.replaceAll("_", " ").replace("file", "").trim()}
                                                                </strong>
                                                                <small>{file.filename ?? `${key}.json`}</small>
                                                            </span>
                                                        </a>
                                                    )
                                            )}
                                        </div>
                                    )}
                                </>
                            )}
                        </section>
                    )}

                    {activeTab === "chapter-extractor" && (
                        <section className="metricsPanel">
                            <div className="panelHeader">
                                <div>
                                    <h2>Chapter extractor</h2>
                                    <p>
                                        Upload an extracted specification JSON file, select a chapter, and export
                                        only the relevant chapter-level JSON.
                                    </p>
                                </div>

                                <span className="statusPill status-idle">Local tool</span>
                            </div>

                            <ChapterExtractionFlow />
                        </section>
                    )}
                </section>
            </section>
        </main>
    );
}

export default App;