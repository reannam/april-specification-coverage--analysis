"""
Centralized path configuration for the entire project.
Ensures consistent path resolution across all modules.
"""

from pathlib import Path

# Get the root directory of the project (april-specification-coverage--analysis)
BASE_DIR = Path(__file__).resolve().parent.parent

# Define all output directories
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR = BASE_DIR / "uploads"

# Subdirectories within outputs
EDGE_CASE_DIR = OUTPUT_DIR / "edge_cases"
COVERAGE_OUTPUT_DIR = OUTPUT_DIR / "coverage_reports"
TRACEABILITY_DIR = OUTPUT_DIR / "traceability"
WEAK_LANGUAGE_DIR = OUTPUT_DIR / "weak_language"
LANGSMITH_LOGS_DIR = OUTPUT_DIR / "langsmith_logs"
USAGE_CHARTS_DIR = OUTPUT_DIR / "usage_charts"
WORKFLOW_IMAGE_DIR = OUTPUT_DIR / "node_architecture_graph"
BLOCKED_TESTS_DIR = OUTPUT_DIR / "blocked_tests"
PRIORITISED_VPLAN_DIR = OUTPUT_DIR / "prioritised_vplans"

# Create all necessary directories
for directory in [
    OUTPUT_DIR,
    UPLOAD_DIR,
    EDGE_CASE_DIR,
    COVERAGE_OUTPUT_DIR,
    TRACEABILITY_DIR,
    WEAK_LANGUAGE_DIR,
    LANGSMITH_LOGS_DIR,
    USAGE_CHARTS_DIR,
    WORKFLOW_IMAGE_DIR,
    BLOCKED_TESTS_DIR,
    PRIORITISED_VPLAN_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)
