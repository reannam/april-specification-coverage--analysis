export type ProcessingStatus =
  | "idle"
  | "ready"
  | "processing"
  | "success"
  | "error";

export type AgentUsage = {
  agent_name: string;
  model_name?: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  total_cost: string | number;
};

export type UsageSummary = {
  prompt_tokens?: number;
  completion_tokens?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  total_cost?: string | number | null;
  agents?: AgentUsage[];
  [key: string]: unknown;
};

export type ScenarioType = "nominal" | "illegal" | "corner";
export type CoverageLabel = "covered" | "partially_covered" | "blocked";
export type TestPriority = 1 | 2 | 3;

export type VPlanTest = {
  test_id: string;
  requirement_id: string;
  requirement_text?: string;
  scenario_type: ScenarioType;
  category: string;
  priority: TestPriority;
  test_description: string;
  test_constraints: string;
  test_steps: string[];
  expected_results: string[];
  coverage: CoverageLabel;
};

export type VPlanMetadata = {
  display_name?: string;
  specification_name?: string;
  section?: string | null;
  requirements_file?: string;
  requirements_file_path?: string;
  [key: string]: unknown;
};

export type VPlanDocument = {
  metadata?: VPlanMetadata;
  feature_list: VPlanTest[];
};

export type EdgeCaseItem = {
  edge_case_id?: string;
  requirement_id?: string;
  requirement_text?: string;
  source_section?: string;
  edge_case_type?: string;
  edge_case_description?: string;
  classification?: string;
  recommended_action?: string;
  [key: string]: unknown;
};

export type EdgeCaseDocument = {
  metadata?: Record<string, unknown>;
  edge_cases: EdgeCaseItem[];
};

export type WeakLanguageIssue = {
  requirement_id?: string;
  requirement_text?: string;
  source_section?: string;
  issue_type?: string;
  matched_words?: string[];
  message?: string;
  [key: string]: unknown;
};

export type WeakLanguageDocument = {
  number_of_language_issues?: number;
  issues: WeakLanguageIssue[];
  [key: string]: unknown;
};

export type AgentResponse = {
  message?: string;
  weak_language?: WeakLanguageDocument;
  edge_cases?: EdgeCaseDocument;
  vplan?: VPlanDocument;

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
  requirement_test_links_download_url?: string | null;
  requirement_test_links_filename?: string | null;
  blocked_test_report_download_url?: string | null;
  blocked_test_report_filename?: string | null;

  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  estimated_cost_usd?: string | number | null;
  agent_usage?: AgentUsage[];
  usage_chart_urls?: Record<string, string>;
  usage_csv_urls?: Record<string, string>;
  requirements_file?: string;
};

export type PrioritiseVPlanResponse = {
  message?: string;
  vplan: VPlanDocument;
  vplan_file: string;
  vplan_filename: string;
  vplan_download_url: string;
};

export type CoverageSummary = {
  total_spec_items?: number;
  covered?: number;
  partially_covered?: number;
  uncovered?: number;
  ambiguity_blocked?: number;
  orphan_vplan_items?: number;
  [key: string]: number | undefined;
};

export type CoveragePercentages = {
  requirement_mapping_coverage?: number;
  weighted_coverage?: number;
  traceability_coverage?: number;
  testability_coverage?: number;
  granularity_adequacy?: number;
  granularity_coverage?: number;
  orphan_rate?: number;
  [key: string]: number | undefined;
};

export type OutputFile = {
  filename?: string | null;
  download_url?: string | null;
};

export type CoverageResponse = {
  message?: string;
  coverage_summary?: CoverageSummary;
  coverage_percentages?: CoveragePercentages;
  coverage_output_files?: Record<string, OutputFile>;
  usage_report_files?: Record<string, OutputFile>;
  coverage_status_download_url?: string | null;
  coverage_status_filename?: string | null;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  estimated_cost_usd?: string | number | null;
  coverage_usage?: UsageSummary;
};
