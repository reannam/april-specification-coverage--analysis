import { useEffect, useMemo, useState } from "react";

import DownloadCard from "../components/common/DownloadCard";
import PageHeader from "../components/common/PageHeader";
import { useWorkflow } from "../context/WorkflowContext";
import { fetchJson } from "../services/api";
import type { EdgeCaseDocument, EdgeCaseItem } from "../types/workflow";
import {
  buildRequirementTextLookup,
  cleanSourceFilename,
  humaniseLabel,
  sectionFromRequirementId,
} from "../utils/formatters";

export default function EdgeCasesPage() {
  const workflow = useWorkflow();
  const [query, setQuery] = useState("");

  const document = workflow.edgeCases ?? workflow.agentResult?.edge_cases ?? null;
  const downloadUrl = workflow.agentResult?.edge_cases_download_url;

  useEffect(() => {
    if (document || !downloadUrl) return;

    fetchJson<EdgeCaseDocument>(downloadUrl)
      .then(workflow.setEdgeCases)
      .catch((error) => console.error("Could not load edge cases:", error));
  }, [document, downloadUrl, workflow.setEdgeCases]);

  const requirementTextLookup = useMemo(
    () =>
      buildRequirementTextLookup(
        workflow.requirementsData,
        workflow.vplan?.feature_list ?? [],
      ),
    [workflow.requirementsData, workflow.vplan],
  );

  const sections = useMemo(() => {
    const grouped = new Map<string, EdgeCaseItem[]>();
    const normalisedQuery = query.trim().toLowerCase();

    for (const item of document?.edge_cases ?? []) {
      const requirementText =
        item.requirement_text ??
        requirementTextLookup.get(item.requirement_id ?? "") ??
        "";

      if (
        normalisedQuery &&
        !JSON.stringify({ item, requirementText })
          .toLowerCase()
          .includes(normalisedQuery)
      ) {
        continue;
      }

      const section =
        item.source_section ?? sectionFromRequirementId(item.requirement_id);
      const current = grouped.get(section) ?? [];
      current.push({ ...item, requirement_text: requirementText });
      grouped.set(section, current);
    }

    return [...grouped.entries()].sort(([first], [second]) =>
      first.localeCompare(second, undefined, { numeric: true }),
    );
  }, [document, query, requirementTextLookup]);

  const count = document?.edge_cases.length ?? 0;
  const sourceName = cleanSourceFilename(
    workflow.agentResult?.requirements_file ??
      workflow.vplan?.metadata?.requirements_file,
  );

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Generated output"
        title="Edge cases"
        description={`${count} edge-case ${count === 1 ? "candidate" : "candidates"}${
          sourceName ? ` from ${sourceName}` : " from the latest run"
        }.`}
        actions={
          downloadUrl ? (
            <DownloadCard
              title="Download edge-case report"
              filename={workflow.agentResult?.edge_cases_filename}
              url={downloadUrl}
            />
          ) : undefined
        }
      />

      {!document ? (
        <div className="empty-state">
          <strong>No edge-case report</strong>
          <p>Generate a vPlan first to create edge-case results.</p>
        </div>
      ) : count === 0 ? (
        <div className="empty-state">
          <strong>No edge cases found</strong>
          <p>No edge-case candidates were identified in this run.</p>
        </div>
      ) : (
        <section className="results-browser">
          <div className="results-browser-toolbar">
            <div>
              <strong>{sections.length} sections</strong>
              <span>{count} edge cases</span>
            </div>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search edge cases"
              aria-label="Search edge cases"
            />
          </div>

          <div className="section-accordion-list">
            {sections.map(([section, records], index) => (
              <details className="section-accordion" key={section} open={index === 0}>
                <summary>
                  <span>{section}</span>
                  <small>{records.length} edge cases</small>
                </summary>

                <div className="section-records">
                  {records.map((item, itemIndex) => (
                    <article
                      className="quality-record"
                      key={item.edge_case_id ?? `${item.requirement_id}-${itemIndex}`}
                    >
                      <header>
                        <strong>{item.requirement_id ?? "Unknown requirement"}</strong>
                        <span>{item.edge_case_id ?? `Edge case ${itemIndex + 1}`}</span>
                      </header>

                      {item.requirement_text ? (
                        <div className="requirement-text-block">
                          <span>Requirement text</span>
                          <p>{item.requirement_text}</p>
                        </div>
                      ) : null}

                      <dl className="readable-details">
                        <div>
                          <dt>Edge case type</dt>
                          <dd>{humaniseLabel(item.edge_case_type ?? "Not specified")}</dd>
                        </div>
                        <div className="wide">
                          <dt>Description</dt>
                          <dd>{item.edge_case_description ?? "Not provided"}</dd>
                        </div>
                        {item.classification ? (
                          <div>
                            <dt>Classification</dt>
                            <dd>{humaniseLabel(item.classification)}</dd>
                          </div>
                        ) : null}
                        {item.recommended_action ? (
                          <div className="wide">
                            <dt>Recommended action</dt>
                            <dd>{item.recommended_action}</dd>
                          </div>
                        ) : null}
                      </dl>
                    </article>
                  ))}
                </div>
              </details>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
