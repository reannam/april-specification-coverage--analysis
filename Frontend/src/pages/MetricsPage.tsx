import DownloadCard from "../components/common/DownloadCard";
import PageHeader from "../components/common/PageHeader";
import { useWorkflow } from "../context/WorkflowContext";
import { getDownloadUrl } from "../services/api";
import type { AgentUsage } from "../types/workflow";
import {
  formatCost,
  formatNumber,
  humaniseLabel,
} from "../utils/formatters";

const sumUsage = (agents: AgentUsage[] | undefined, key: keyof AgentUsage) => {
  if (!agents?.length) return undefined;
  return agents.reduce((total, agent) => total + Number(agent[key] ?? 0), 0);
};

export default function MetricsPage() {
  const { agentResult, coverageResult } = useWorkflow();
  const generationAgents = agentResult?.agent_usage ?? [];
  const coverageUsage = coverageResult?.coverage_usage;

  const generationInput =
    agentResult?.input_tokens ?? sumUsage(generationAgents, "prompt_tokens");
  const generationOutput =
    agentResult?.output_tokens ?? sumUsage(generationAgents, "completion_tokens");
  const generationTotal =
    agentResult?.total_tokens ?? sumUsage(generationAgents, "total_tokens");
  const generationCost =
    agentResult?.estimated_cost_usd ?? sumUsage(generationAgents, "total_cost");

  const coverageInput =
    coverageResult?.input_tokens ??
    coverageUsage?.input_tokens ??
    coverageUsage?.prompt_tokens;
  const coverageOutput =
    coverageResult?.output_tokens ??
    coverageUsage?.output_tokens ??
    coverageUsage?.completion_tokens;
  const coverageTotal = coverageResult?.total_tokens ?? coverageUsage?.total_tokens;
  const coverageCost =
    coverageResult?.estimated_cost_usd ?? coverageUsage?.total_cost;

  const cards = [
    ["Generation total tokens", formatNumber(generationTotal)],
    ["Generation input tokens", formatNumber(generationInput)],
    ["Generation output tokens", formatNumber(generationOutput)],
    ["Generation cost", formatCost(generationCost)],
    ["Coverage total tokens", formatNumber(coverageTotal)],
    ["Coverage input tokens", formatNumber(coverageInput)],
    ["Coverage output tokens", formatNumber(coverageOutput)],
    ["Coverage cost", formatCost(coverageCost)],
  ];

  const coverageFiles = Object.entries(coverageResult?.usage_report_files ?? {});
  const coverageCharts = coverageFiles.filter(([, file]) =>
    file.filename?.toLowerCase().endsWith(".png"),
  );
  const coverageDownloads = coverageFiles.filter(
    ([, file]) => !file.filename?.toLowerCase().endsWith(".png"),
  );

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Reports"
        title="Usage and cost"
        description="Token usage and estimated model cost for the latest generation and coverage runs."
      />

      <div className="metric-grid">
        {cards.map(([label, value]) => (
          <div className="metric-card" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>

      <section className="report-section">
        <h2>Downloads</h2>
        <div className="download-grid">
          {agentResult?.langsmith_log_download_url ? (
            <DownloadCard
              title="Generation usage log"
              filename={agentResult.langsmith_log_filename}
              url={agentResult.langsmith_log_download_url}
            />
          ) : null}

          {Object.entries(agentResult?.usage_csv_urls ?? {}).map(([name, url]) => (
            <DownloadCard
              key={name}
              title={humaniseLabel(name)}
              filename={url.split("/").pop()}
              url={url}
            />
          ))}

          {coverageDownloads.map(([name, file]) => (
            <DownloadCard
              key={name}
              title={humaniseLabel(name)}
              filename={file.filename}
              url={file.download_url}
            />
          ))}
        </div>
      </section>

      {generationAgents.length > 0 ? (
        <section className="panel table-panel">
          <h2>Agent usage</h2>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Model</th>
                  <th>Input</th>
                  <th>Output</th>
                  <th>Total</th>
                  <th>Cost</th>
                </tr>
              </thead>
              <tbody>
                {generationAgents.map((agent, index) => (
                  <tr key={`${agent.agent_name}-${index}`}>
                    <td>{humaniseLabel(agent.agent_name)}</td>
                    <td>{agent.model_name ?? "—"}</td>
                    <td>{formatNumber(agent.prompt_tokens)}</td>
                    <td>{formatNumber(agent.completion_tokens)}</td>
                    <td>{formatNumber(agent.total_tokens)}</td>
                    <td>{formatCost(agent.total_cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {Object.keys(agentResult?.usage_chart_urls ?? {}).length > 0 ||
      coverageCharts.length > 0 ? (
        <section className="report-section">
          <h2>Usage charts</h2>
          <div className="chart-grid">
            {Object.entries(agentResult?.usage_chart_urls ?? {}).map(([name, url]) => (
              <article className="chart-card" key={name}>
                <h3>{humaniseLabel(name)}</h3>
                <img src={getDownloadUrl(url)} alt={humaniseLabel(name)} />
              </article>
            ))}

            {coverageCharts.map(([name, file]) => (
              <article className="chart-card" key={name}>
                <h3>{humaniseLabel(name)}</h3>
                <img
                  src={getDownloadUrl(file.download_url)}
                  alt={humaniseLabel(name)}
                />
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
