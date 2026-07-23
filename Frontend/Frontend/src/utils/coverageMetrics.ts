import type { CoverageResponse } from "../types/workflow";
import { humaniseLabel } from "./formatters";

export type MetricExplanation = {
  title: string;
  definition: string;
  formula: string;
  detailKey: string;
};

const explanations: Record<string, Omit<MetricExplanation, "title">> = {
  requirement_mapping_coverage: {
    definition: "Percentage of specification requirements linked to at least one vPlan item.",
    formula: "(mapped specification items ÷ total specification items) × 100",
    detailKey: "requirement_mapping",
  },
  weighted_coverage: {
    definition: "Coverage that scores covered requirements as 1, partially covered as 0.5, and uncovered or ambiguous requirements as 0.",
    formula: "sum(requirement coverage scores) ÷ total requirements × 100",
    detailKey: "weighted_coverage",
  },
  traceability_coverage: {
    definition: "Percentage of vPlan items that cite a source requirement or section.",
    formula: "(vPlan items with source trace ÷ total vPlan items) × 100",
    detailKey: "traceability",
  },
  testability_coverage: {
    definition: "Percentage of mapped specification items with a testable vPlan entry.",
    formula: "(mapped items with a testable entry ÷ mapped specification items) × 100",
    detailKey: "testability",
  },
  granularity_adequacy: {
    definition: "Percentage of mapped requirements covered at suitable behavioural detail.",
    formula: "(requirements covered at suitable detail ÷ mapped requirements) × 100",
    detailKey: "granularity_adequacy",
  },
  granularity_coverage: {
    definition: "Percentage of mapped requirements covered at suitable behavioural detail.",
    formula: "(requirements covered at suitable detail ÷ mapped requirements) × 100",
    detailKey: "granularity_adequacy",
  },
  orphan_rate: {
    definition: "Percentage of vPlan items that do not trace to any specification requirement.",
    formula: "(orphan vPlan items ÷ total vPlan items) × 100",
    detailKey: "orphan_rate",
  },
  ambiguity_uncovered_rate: {
    definition: "Percentage of specification items that are uncovered with linked ambiguity evidence.",
    formula: "(items uncovered due to ambiguity ÷ total specification items) × 100",
    detailKey: "ambiguity_uncovered",
  },
};

export const explainMetric = (key: string): MetricExplanation => {
  const known = explanations[key];
  if (known) return { title: humaniseLabel(key), ...known };

  return {
    title: humaniseLabel(key),
    definition: `The reported count for ${humaniseLabel(key).toLowerCase()}.`,
    formula: "Counted from the verified requirement and vPlan records shown below.",
    detailKey: key.startsWith("granularity_")
      ? "granularity_adequacy"
      : key === "orphan_vplan_items"
        ? "orphan_rate"
        : "coverage_status",
  };
};

export const metricValue = (result: CoverageResponse, key: string) =>
  result.coverage_percentages?.[key] ?? result.coverage_summary?.[key];

const statusForSummaryKey: Record<string, string> = {
  covered: "Covered",
  partially_covered: "Partially covered",
  uncovered: "Uncovered",
  ambiguity_uncovered: "Ambiguous / not yet plannable",
};

export const metricDetails = (result: CoverageResponse, key: string): unknown => {
  // Summary cards use the verifier's requirement-level decisions. These are the
  // final coverage decisions; the earlier vPlan labels are only supporting data.
  const details = result.coverage_details ?? {};
  const explanation = explainMetric(key);

  if (statusForSummaryKey[key]) {
    const coverageStatus = details.coverage_status as Record<string, unknown> | undefined;
    const requirements = Array.isArray(coverageStatus?.labelled_requirements)
      ? coverageStatus.labelled_requirements
      : [];

    return {
      requirements: requirements.filter((item) => {
        if (!item || typeof item !== "object") return false;
        return (item as Record<string, unknown>).verified_coverage_status === statusForSummaryKey[key];
      }),
    };
  }

  if (key === "total_spec_items") {
    return details.coverage_status ?? {};
  }

  return details[explanation.detailKey] ?? {};
};
