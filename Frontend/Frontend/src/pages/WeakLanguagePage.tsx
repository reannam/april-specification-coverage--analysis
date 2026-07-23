import { useEffect, useMemo, useState } from "react";

import DownloadCard from "../components/common/DownloadCard";
import HighlightedText from "../components/common/HighlightedText";
import PageHeader from "../components/common/PageHeader";
import { useWorkflow } from "../context/WorkflowContext";
import { fetchJson } from "../services/api";
import type { WeakLanguageDocument, WeakLanguageIssue } from "../types/workflow";
import {
  buildRequirementTextLookup,
  cleanSourceFilename,
  humaniseLabel,
  sectionFromRequirementId,
} from "../utils/formatters";

type RequirementIssues = {
  requirementId: string;
  requirementText: string;
  issues: WeakLanguageIssue[];
};

export default function WeakLanguagePage() {
  const workflow = useWorkflow();
  const [query, setQuery] = useState("");

  const document =
    workflow.weakLanguage ?? workflow.agentResult?.weak_language ?? null;
  const downloadUrl = workflow.agentResult?.weak_words_download_url;

  useEffect(() => {
    if (document || !downloadUrl) return;

    fetchJson<WeakLanguageDocument>(downloadUrl)
      .then(workflow.setWeakLanguage)
      .catch((error) => {
        console.error("Could not load weak-language report:", error);
      });
  }, [document, downloadUrl, workflow.setWeakLanguage]);

  const requirementTextLookup = useMemo(
    () =>
      buildRequirementTextLookup(
        workflow.requirementsData,
        workflow.vplan?.feature_list ?? [],
      ),
    [workflow.requirementsData, workflow.vplan],
  );

  const sections = useMemo(() => {
    const normalisedQuery = query.trim().toLowerCase();
    const requirements = new Map<string, RequirementIssues>();

    for (const issue of document?.issues ?? []) {
      const requirementId = issue.requirement_id ?? "Unknown requirement";
      const requirementText =
        issue.requirement_text ?? requirementTextLookup.get(requirementId) ?? "";

      const searchable = JSON.stringify({ issue, requirementText }).toLowerCase();
      if (normalisedQuery && !searchable.includes(normalisedQuery)) continue;

      const current = requirements.get(requirementId) ?? {
        requirementId,
        requirementText,
        issues: [],
      };
      current.issues.push(issue);
      if (!current.requirementText && requirementText) {
        current.requirementText = requirementText;
      }
      requirements.set(requirementId, current);
    }

    const grouped = new Map<string, RequirementIssues[]>();
    for (const item of requirements.values()) {
      const section =
        item.issues.find((issue) => issue.source_section)?.source_section ??
        sectionFromRequirementId(item.requirementId);
      const current = grouped.get(section) ?? [];
      current.push(item);
      grouped.set(section, current);
    }

    return [...grouped.entries()]
      .map(([section, records]) => [
        section,
        records.sort((first, second) =>
          first.requirementId.localeCompare(second.requirementId, undefined, {
            numeric: true,
          }),
        ),
      ] as const)
      .sort(([first], [second]) =>
        first.localeCompare(second, undefined, { numeric: true }),
      );
  }, [document, query, requirementTextLookup]);

  const issues = document?.issues ?? [];
  const issueCount = document?.number_of_language_issues ?? issues.length;
  const sourceName = cleanSourceFilename(
    workflow.agentResult?.requirements_file ??
      workflow.vplan?.metadata?.requirements_file,
  );

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Requirement quality"
        title="Weak language"
        description={`${issueCount} language ${
          issueCount === 1 ? "issue" : "issues"
        } found${sourceName ? ` in ${sourceName}` : " in the latest run"}.`}
        actions={
          downloadUrl ? (
            <DownloadCard
              title="Download weak-language report"
              filename={workflow.agentResult?.weak_words_filename}
              url={downloadUrl}
            />
          ) : undefined
        }
      />

      {!document ? (
        <div className="empty-state">
          <strong>No weak-language report</strong>
          <p>Generate a vPlan first to produce the weak-language report.</p>
        </div>
      ) : issues.length === 0 ? (
        <div className="empty-state">
          <strong>No weak language found</strong>
          <p>The checker did not identify any language issues in this run.</p>
        </div>
      ) : (
        <section className="results-browser">
          <div className="results-browser-toolbar">
            <div>
              <strong>{sections.length} sections</strong>
              <span>{issueCount} issues</span>
            </div>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search requirements or issues"
              aria-label="Search weak-language results"
            />
          </div>

          <div className="section-accordion-list">
            {sections.map(([section, records], sectionIndex) => (
              <details
                className="section-accordion"
                key={section}
                open={sectionIndex === 0}
              >
                <summary>
                  <span>{section}</span>
                  <small>
                    {records.length} requirements ·{" "}
                    {records.reduce((total, record) => total + record.issues.length, 0)} issues
                  </small>
                </summary>

                <div className="section-records">
                  {records.map((record) => {
                    const matchedWords = record.issues.flatMap(
                      (issue) => issue.matched_words ?? [],
                    );

                    return (
                      <article className="quality-record" key={record.requirementId}>
                        <header>
                          <strong>{record.requirementId}</strong>
                          <span>{record.issues.length} issues</span>
                        </header>

                        <div className="requirement-text-block">
                          <span>Requirement text</span>
                          <p>
                            {record.requirementText ? (
                              <HighlightedText
                                text={record.requirementText}
                                terms={matchedWords}
                              />
                            ) : (
                              "Requirement text was not included in the current outputs."
                            )}
                          </p>
                        </div>

                        <div className="issue-list">
                          {record.issues.map((issue, index) => (
                            <div className="issue-item" key={`${issue.issue_type}-${index}`}>
                              <div className="issue-item-heading">
                                <strong>
                                  {humaniseLabel(issue.issue_type ?? "Language issue")}
                                </strong>
                                {issue.matched_words?.length ? (
                                  <span>{issue.matched_words.join(", ")}</span>
                                ) : null}
                              </div>
                              <p>{issue.message ?? "No explanation was provided."}</p>
                            </div>
                          ))}
                        </div>
                      </article>
                    );
                  })}
                </div>
              </details>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
