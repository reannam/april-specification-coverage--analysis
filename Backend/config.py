"""Single source of truth for project paths and runtime directories.

Modules should import paths from here instead of deriving their own project root.
Keeping that rule prevents the CLI, API, and tests from writing to different places
when their current working directories differ.
"""

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent

# Kept as a public alias because entry points already use this name.
BASE_DIR = PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "outputs"
UPLOAD_DIR = PROJECT_ROOT / "uploads"

# Runtime directories. New output types should be added here before being used.
VPLAN_DIR = OUTPUT_DIR
EDGE_CASE_DIR = OUTPUT_DIR / "edge_cases"
TRACEABILITY_DIR = OUTPUT_DIR / "traceability"
WEAK_LANGUAGE_DIR = OUTPUT_DIR / "weak_language"
LANGSMITH_LOGS_DIR = OUTPUT_DIR / "langsmith_logs"
USAGE_CHARTS_DIR = OUTPUT_DIR / "usage_charts"
WORKFLOW_IMAGE_DIR = OUTPUT_DIR / "node_architecture_graph"
UNCOVERED_TESTS_DIR = OUTPUT_DIR / "uncovered_tests"
PRIORITISED_VPLAN_DIR = OUTPUT_DIR / "prioritised_vplans"
COVERAGE_STATUS_DIR = OUTPUT_DIR / "coverage_status"
FINAL_COVERAGE_DIR = OUTPUT_DIR / "final_coverage_report"
COVERAGE_UPLOAD_CACHE_DIR = OUTPUT_DIR / "coverage_upload_cache"
PREPROCESSED_REQUIREMENTS_DIR = UPLOAD_DIR / "preprocessed"
ANALYSIS_OUTPUT_DIR = OUTPUT_DIR / "analysis_and_comparison"
SPEC_COMPARISON_DIR = ANALYSIS_OUTPUT_DIR / "specification_comparisons"
QUALITY_REPORT_DIR = ANALYSIS_OUTPUT_DIR / "quality_reports"
EXTRACTION_OUTPUT_DIR = OUTPUT_DIR / "extraction"
EXTRACTION_TABLE_DIR = EXTRACTION_OUTPUT_DIR / "tables"
MATPLOTLIB_CONFIG_DIR = OUTPUT_DIR / "matplotlib_cache"
os.environ.setdefault("MPLCONFIGDIR", str(MATPLOTLIB_CONFIG_DIR))

# Files shared by several modules also belong here so their locations cannot drift.
COVERAGE_TERMS_FILE = PACKAGE_DIR / "Coverage" / "coverage_terms.txt"
WEAK_LANGUAGE_TERMS_FILE = (
    PACKAGE_DIR / "vPlan" / "report_generation" / "regex_config.txt"
)
MASTER_USAGE_FILE = LANGSMITH_LOGS_DIR / "all_usage_runs.json"
VPLAN_WORKFLOW_USAGE_SOURCE = OUTPUT_DIR / "vplan_workflow.json"
COVERAGE_WORKFLOW_USAGE_SOURCE = OUTPUT_DIR / "coverage_workflow.json"
VPLAN_WORKFLOW_IMAGE_PATH = WORKFLOW_IMAGE_DIR / "vplan-architecture.png"
COVERAGE_WORKFLOW_IMAGE_PATH = WORKFLOW_IMAGE_DIR / "coverage-architecture.png"

# The API resolves downloads by basename. Search order is explicit because duplicate
# basenames in multiple directories would otherwise produce non-deterministic results.
DOWNLOAD_SEARCH_DIRS = (
    VPLAN_DIR,
    EDGE_CASE_DIR,
    LANGSMITH_LOGS_DIR,
    TRACEABILITY_DIR,
    UNCOVERED_TESTS_DIR,
    COVERAGE_STATUS_DIR,
    FINAL_COVERAGE_DIR,
    USAGE_CHARTS_DIR,
    WEAK_LANGUAGE_DIR,
    COVERAGE_UPLOAD_CACHE_DIR,
    PRIORITISED_VPLAN_DIR,
    SPEC_COMPARISON_DIR,
    QUALITY_REPORT_DIR,
    EXTRACTION_OUTPUT_DIR,
    EXTRACTION_TABLE_DIR,
    MATPLOTLIB_CONFIG_DIR,
)

# Comma-separated override is useful when the frontend runs on another local port.
CORS_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
)

# Mermaid PNG rendering may use a remote renderer. Keep it off during normal API
# startup; developers can opt in when they intentionally want refreshed diagrams.
GENERATE_WORKFLOW_IMAGES = os.getenv(
    "GENERATE_WORKFLOW_IMAGES", "false"
).casefold() in {
    "1",
    "true",
    "yes",
    "on",
}

# Shared limits keep both model-assisted coverage reviewers bounded and visible.
COVERAGE_MODEL_BATCH_SIZE = max(1, int(os.getenv("COVERAGE_MODEL_BATCH_SIZE", "10")))
COVERAGE_MODEL_BATCH_RETRIES = max(
    0, int(os.getenv("COVERAGE_MODEL_BATCH_RETRIES", "2"))
)

# Requirement categorisation first derives one bounded taxonomy from the complete
# specification, then assigns requirements in smaller structured-output calls.
REQUIREMENT_CATEGORY_MODEL = os.getenv(
    "REQUIREMENT_CATEGORY_MODEL", "openai:gpt-5.6-terra"
)
REQUIREMENT_CATEGORY_BATCH_SIZE = max(
    1, int(os.getenv("REQUIREMENT_CATEGORY_BATCH_SIZE", "100"))
)
REQUIREMENT_CATEGORY_BATCH_RETRIES = max(
    0, int(os.getenv("REQUIREMENT_CATEGORY_BATCH_RETRIES", "2"))
)
MAX_PRIORITY_SELECTIONS = max(2, int(os.getenv("MAX_PRIORITY_SELECTIONS", "12")))

# Directory creation is intentionally centralised and idempotent.
RUNTIME_DIRECTORIES = (
    OUTPUT_DIR,
    UPLOAD_DIR,
    EDGE_CASE_DIR,
    TRACEABILITY_DIR,
    WEAK_LANGUAGE_DIR,
    LANGSMITH_LOGS_DIR,
    USAGE_CHARTS_DIR,
    WORKFLOW_IMAGE_DIR,
    UNCOVERED_TESTS_DIR,
    PRIORITISED_VPLAN_DIR,
    COVERAGE_STATUS_DIR,
    FINAL_COVERAGE_DIR,
    COVERAGE_UPLOAD_CACHE_DIR,
    PREPROCESSED_REQUIREMENTS_DIR,
    ANALYSIS_OUTPUT_DIR,
    SPEC_COMPARISON_DIR,
    QUALITY_REPORT_DIR,
    EXTRACTION_OUTPUT_DIR,
    EXTRACTION_TABLE_DIR,
)

for directory in RUNTIME_DIRECTORIES:
    directory.mkdir(parents=True, exist_ok=True)
