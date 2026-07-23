import { Link, Navigate, useParams } from "react-router-dom";

import PageHeader from "../components/common/PageHeader";
import { useWorkflow } from "../context/WorkflowContext";
import { humaniseLabel } from "../utils/formatters";
import {
  explainMetric,
  metricDetails,
  metricValue,
} from "../utils/coverageMetrics";

type JsonObject = Record<string, unknown>;

const isObject = (value: unknown): value is JsonObject =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const recordTitle = (record: JsonObject, index: number) =>
  String(
    record.requirement_id ??
      record.test_id ??
      record.id ??
      record.source_section ??
      `Item ${index + 1}`,
  );

function ReadableValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    if (!value.length) return <span>None</span>;
    return (
      <ul>
        {value.map((item, index) => (
          <li key={index}>
            {isObject(item) ? <ReadableObject value={item} /> : String(item)}
          </li>
        ))}
      </ul>
    );
  }

  if (isObject(value)) return <ReadableObject value={value} />;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  return <span>{String(value ?? "Not provided")}</span>;
}

function ReadableObject({ value }: { value: JsonObject }) {
  return (
    <dl className="coverage-record-details">
      {Object.entries(value).map(([key, field]) => (
        <div key={key}>
          <dt>{humaniseLabel(key)}</dt>
          <dd><ReadableValue value={field} /></dd>
        </div>
      ))}
    </dl>
  );
}

export default function CoverageMetricPage() {
  const { metricKey = "" } = useParams();
  const { coverageResult } = useWorkflow();

  if (!coverageResult) return <Navigate to="/verification/coverage" replace />;

  const explanation = explainMetric(metricKey);
  const value = metricValue(coverageResult, metricKey);
  const details = metricDetails(coverageResult, metricKey);
  const detailObject = isObject(details) ? details : { issues: details };
  const arrays = Object.entries(detailObject)
    .filter(([, item]) => Array.isArray(item))
    .map(([section, item]) => [section, item as unknown[]] as const);
  const overview = Object.fromEntries(
    Object.entries(detailObject).filter(([, item]) => !Array.isArray(item)),
  );
  const isPercentage = metricKey in (coverageResult.coverage_percentages ?? {});

  return (
    <div className="stack-lg">
      <Link className="back-link" to="/verification/coverage">← Back to coverage</Link>

      <PageHeader
        eyebrow="Coverage calculation"
        title={explanation.title}
        description={explanation.definition}
      />

      <section className="metric-explanation panel">
        <div><span>Score</span><strong>{value === undefined ? "—" : `${value}${isPercentage ? "%" : ""}`}</strong></div>
        <div><span>Formula</span><code>{explanation.formula}</code></div>
      </section>

      {Object.keys(overview).length > 0 && (
        <section className="panel">
          <h2>Calculation inputs</h2>
          <ReadableObject value={overview} />
        </section>
      )}

      {arrays.map(([section, records]) => (
        <section className="coverage-detail-section" key={section}>
          <div className="section-heading">
            <div><h2>{humaniseLabel(section)}</h2><p>{records.length} records</p></div>
          </div>
          <div className="section-accordion-list panel compact-panel">
            {records.length ? records.map((record, index) => {
              const object = isObject(record) ? record : { value: record };
              return (
                <details className="section-accordion" key={`${recordTitle(object, index)}-${index}`} open={index === 0}>
                  <summary><span>{recordTitle(object, index)}</span><small>View details</small></summary>
                  <div className="coverage-record"><ReadableObject value={object} /></div>
                </details>
              );
            }) : <div className="empty-state"><strong>No issues in this section</strong></div>}
          </div>
        </section>
      ))}

      {!arrays.length && !Object.keys(overview).length && (
        <div className="empty-state"><strong>No supporting records were returned for this metric.</strong></div>
      )}
    </div>
  );
}
