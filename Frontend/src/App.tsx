import {useRef, useState} from "react";
import "./App.css";

type ProcessingStatus = "idle" | "ready" | "processing" | "success" | "error";
type ActiveTab = "analysis" | "metrics";

type AgentUsage = {
    agent_name: string;
    model_name?: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    total_cost: string;
};

type AgentResponse = {
    message?: string;

    vplan_download_url: string;
    edge_cases_download_url: string;

    vplan_filename?: string;
    edge_cases_filename?: string;

    langsmith_log_download_url?: string | null;
    langsmith_log_filename?: string | null;

    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
    estimated_cost_usd?: string;

    agent_usage?: AgentUsage[];

    usage_chart_urls?: Record<string, string>;
    usage_csv_urls?: Record<string, string>;
};

const API_BASE_URL = "http://localhost:8000";

function App() {
    const [activeTab, setActiveTab] = useState<ActiveTab>("analysis");
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [status, setStatus] = useState<ProcessingStatus>("idle");
    const [errorMessage, setErrorMessage] = useState<string>("");
    const [result, setResult] = useState<AgentResponse | null>(null);
    const [progress, setProgress] = useState<number>(0);

    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const progressIntervalRef = useRef<number | null>(null);

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

    const resetState = () => {
        stopFakeProgress();
        setSelectedFile(null);
        setStatus("idle");
        setErrorMessage("");
        setResult(null);
        setProgress(0);

        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];

        setErrorMessage("");
        setResult(null);
        setProgress(0);

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
        setErrorMessage("");
        setResult(null);
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

    const getDownloadUrl = (url: string) => {
        if (url.startsWith("http")) return url;
        return `${API_BASE_URL}${url}`;
    };

    const formatNumber = (value?: number) => {
        if (value === undefined || value === null) return "Not available";
        return value.toLocaleString();
    };

    const formatCost = (value?: string) => {
        if (!value) return "Not available";
        return value;
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
                            the generated vPlan and edge-case analysis files.
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
                                <strong>Review metrics</strong>
                                <p>Check token usage and cost information for the latest run.</p>
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
                            Run Analysis
                        </button>

                        <button
                            className={`tabButton ${activeTab === "metrics" ? "active" : ""}`}
                            onClick={() => setActiveTab("metrics")}
                            type="button"
                        >
                            Run Metrics
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
                                    disabled={status === "processing"}
                                />

                                <label htmlFor="requirements-file" className="uploadLabel">
                                    <span className="uploadIcon">↑</span>

                                    <span className="uploadText">
                    <strong>{selectedFile ? selectedFile.name : "Choose requirements JSON"}</strong>
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
                                        <div className="spinner"/>
                                        <div>
                                            <strong>Processing requirements</strong>
                                            <p>Running vPlan generation and edge-case extraction.</p>
                                        </div>
                                    </div>

                                    <div className="progressOuter" aria-label="Processing progress">
                                        <div className="progressInner" style={{width: `${progress}%`}}/>
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
                        <small>{result.edge_cases_filename ?? "generated_edge_cases.json"}</small>
                      </span>
                                        </a>
                                    </div>
                                </div>
                            )}

                            <div className="actions">
                                <button
                                    className="primaryButton"
                                    onClick={handleGenerate}
                                    disabled={!selectedFile || status === "processing"}
                                    type="button"
                                >
                                    {status === "processing" ? "Generating..." : "Generate outputs"}
                                </button>

                                <button
                                    className="ghostButton"
                                    onClick={resetState}
                                    disabled={status === "processing"}
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
                                                <small>{result.langsmith_log_filename ?? "Download token and cost log"}</small>
                                            </span>
                                        </a>
                                    ) : (
                                        <div className="emptyState">
                                            <strong>LangSmith log not connected yet</strong>
                                            <p>
                                                The metrics tab is ready, but the backend response does not currently
                                                include
                                                token or cost information.
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
                                                {Object.entries(result.usage_chart_urls).map(([chartName, chartUrl]) => (
                                                    <article className="chartCard" key={chartName}>
                                                        <h3>{chartName.replaceAll("_", " ")}</h3>
                                                        <img
                                                            src={getDownloadUrl(chartUrl)}
                                                            alt={chartName.replaceAll("_", " ")}
                                                        />
                                                    </article>
                                                ))}
                                            </div>
                                        </section>
                                    )}
                                </>
                            )}
                        </section>
                    )}
                </section>
            </section>
        </main>
    );
}

export default App;