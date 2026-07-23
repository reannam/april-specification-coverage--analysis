# Specification Coverage Analysis

AI-assisted verification planning for structured semiconductor requirements. The repository contains a FastAPI backend and a React/Vite frontend.

The implemented workflow accepts a JSON object containing a top-level `requirements` array and produces:

- a requirement-linked vPlan;
- concise model-generated test names with deterministic cleanup and fallbacks;
- edge-case and deterministic weak-language reports;
- requirement-to-test traceability;
- uncovered and partially covered test information;
- deterministic and model-assisted coverage metrics, gap reports, and ambiguity reports;
- extracted-specification version comparison in JSON, CSV, and Markdown;
- extraction completeness, accuracy, and table/figure capture analysis;
- deterministic PDF-to-JSON and requirements extraction;
- token, cost, and trace metadata.

Generated results are engineering aids, not sign-off artefacts. A verification engineer should review them before use.

For detailed operating instructions, every output field, score formula, authority order, and known limitation, see [USER_GUIDE.md](USER_GUIDE.md).

## Current workflow

1. Preprocess the uploaded document to retain its `requirements` array.
2. Use GPT-5.6 Terra by default to derive one bounded whole-specification requirement taxonomy, then assign every requirement to a parent and subcategory in batches.
3. Run deterministic weak-language checks.
4. Use GPT-5.4 to extract relevant edge cases.
5. Use GPT-5.4 to generate vPlan rows in parent-category batches, keeping subcategories contiguous.
6. Use GPT-5.4-mini to assign consistent test-level categories and concise test names. Names are normalised and receive deterministic description-based fallbacks when necessary.
7. Export traceability and uncovered-test reports.
8. Run bounded, progress-logged coverage checks on the requirements, vPlan, edge cases, and weak-language report.

Coverage includes requirement mapping, weighted full/partial coverage, traceability, testability, granularity adequacy, orphan rate, gaps, and ambiguity-related limitations. The UI exposes the formula and supporting records for each displayed metric.

Uncovered rows are traceability-only: they contain no test name, test description, steps, or expected results. Covered and partially covered rows must contain a specific description, at least one executable step, and at least one observable expected result. Final coverage files re-evaluate vPlan labels and are authoritative when the values differ.

## Repository structure

```text
Backend/
  vPlan/               vPlan agents, scheduling, reporting and post-processing
  Coverage/            coverage calculations and final reports
  AnalyseAndCompareSpecs/
                       version comparison and extraction-quality analysis
  Extraction/          PDF parsing, extraction regexes and requirements export
  config.py            single source of truth for runtime paths and directories
  api.py                FastAPI endpoints and downloads
Frontend/
  src/components/      shared layout and result components
  src/context/         cached workflow state
  src/pages/           routed workflow and report pages
  src/services/        API helpers
  src/types/           API and document types
tests/                  backend unit tests
outputs/                runtime-generated files; not source data
uploads/                runtime upload cache
```

Do not commit `.env`, virtual environments, upload caches, generated outputs, or API keys.

## Requirements

- Python 3.11+
- Node.js 18+
- npm
- an OpenAI API key
- optional LangSmith credentials for tracing

## Setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r Backend/requirements.txt
```

If an existing virtual environment predates PDF extraction, refresh it with the
command above or install the new dependency directly:

```bash
python -m pip install pymupdf
```

Use `python -m pip` while the same environment that runs `uvicorn` is active;
this prevents the package being installed into a different Python interpreter.

On Windows, activate with `.venv\Scripts\activate`.

Create a repository-root `.env` file:

```env
OPENAI_API_KEY=replace_me

# Optional tracing
LANGSMITH_API_KEY=replace_me
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=specification-analysis

# Optional model/batching overrides
REQUIREMENT_CATEGORY_MODEL=openai:gpt-5.6-terra
REQUIREMENT_CATEGORY_BATCH_SIZE=100
REQUIREMENT_CATEGORY_BATCH_RETRIES=2
CATEGORY_MODEL=openai:gpt-5.4-mini
CATEGORY_BATCH_SIZE=24
CATEGORY_MAX_WORKERS=2
CATEGORY_BATCH_RETRIES=1
VPLAN_BATCH_RETRIES=2
VPLAN_CATEGORY_BATCH_SIZE=40
MAX_PRIORITY_SELECTIONS=12
COVERAGE_MODEL_BATCH_SIZE=10
COVERAGE_MODEL_BATCH_RETRIES=2
INCONSISTENCY_MODEL=gpt-5.6-sol
INCONSISTENCY_AGENT_COUNT=6
GRANULARITY_MODEL=openai:gpt-5.4
TESTABILITY_MODEL=openai:gpt-5.4
```

Install the frontend:

```bash
cd Frontend
npm install
```

## Run locally

Start the backend from the repository root:

```bash
uvicorn Backend.api:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd Frontend
npm run dev
```

The UI defaults to `http://localhost:5173` and the API to `http://localhost:8000`. Set `VITE_API_BASE_URL` before starting Vite to use another API origin. Configure allowed frontend origins with the comma-separated `CORS_ORIGINS` environment variable. Workflow diagram rendering is disabled because it may use a remote Mermaid renderer; set `GENERATE_WORKFLOW_IMAGES=true` only when intentionally refreshing diagrams.

The backend can also be run directly:

```bash
python -m Backend.vPlan.main path/to/requirements.json
```

## API

- `GET /api/health` — service health.
- `POST /api/extract-pdf` — upload a PDF; returns the complete structured document.
- `POST /api/extract-requirements` — derive vPlan-ready requirements from extracted document JSON.
- `POST /api/run-agents` — upload `requirements_file`; returns vPlan, edge-case, weak-language and traceability outputs.
- `POST /api/run-coverage` — use cached paths or upload all four coverage inputs.
- `POST /api/prioritise-vplan` — apply deterministic category-based priorities.
- `POST /api/compare-specifications` — compare older and newer extractor JSON files.
- `POST /api/check-inconsistencies` — run independent internal-consistency reviews of one specification PDF.
- `POST /api/check-specification-quality` — score extractor JSON, optionally using its source PDF and a gold JSON.
- `GET /api/download/{filename}` — download generated JSON/CSV files.
- `GET /api/usage-chart/{filename}` — download generated usage charts or CSVs.

## Input format

The uploaded JSON must be an object with a top-level `requirements` list. A raw top-level list is not accepted by the current preprocessor.

```json
{
  "requirements": [
    {
      "id": "REQ_I2C_001",
      "description": "The controller must support normal-mode operation.",
      "text": "The controller shall support 100 Kbps I2C operation.",
      "source_section": "1.1 I2C Features",
      "signals": ["scl", "sda"],
      "type": "functional_requirement"
    }
  ]
}
```

Unique, non-empty requirement IDs are essential. Duplicate IDs make mapping and coverage results unreliable.

## Frontend status

### Extract from PDF and extract requirements

Implemented as four distinct stages: **Extract from PDF → Extract requirements → Generate vPlan → Check coverage**. PDF extraction creates complete document JSON and table CSVs. The requirements page then validates and refines that document into the compact vPlan input; only this second stage selects a file for vPlan generation.

### Check for Inconsistencies

Implemented. Upload one complete specification PDF. Independent structured-output reviewers identify explicit internal contradictions, and deterministic voting retains only findings that reach the configured majority threshold. Consensus and individual reviewer JSON files can be inspected and downloaded.

### Compare specification versions

Implemented. Upload two extractor JSON versions, inspect grouped expandable changes, and download CSV, JSON, or Markdown reports.

### Quality checker

Implemented as a separate item under **Analyse and compare**. Upload extractor JSON and optionally its source PDF and a manually checked gold-reference JSON to calculate and download extraction-quality results.

## Known pitfalls and limitations

- Model output is non-deterministic. Structured schemas, deterministic cleanup, and retries reduce failures but do not prove technical correctness.
- Test names are based on descriptions; vague descriptions produce vague names. The deterministic fallback truncates to eight words and may be less polished than a model result.
- The requirement taxonomy is generated once from the whole specification with GPT-5.6 Terra by default, then assigned in bounded batches. It is more consistent than free-form per-batch labels but still requires engineering review.
- Large specifications can be slow and expensive. Categorisation, vPlan, and coverage batching protect structured-output limits but do not remove model cost.
- Parent requirement categories are capped at 12 and refined by subcategories. Oversized parents are still split, so relationships across those chunks can be missed.
- Granularity and testability use model judgements, while most other coverage calculations are deterministic. Scores are therefore not all equally reproducible.
- Coverage depends on exact requirement IDs. Missing or duplicate IDs can distort traceability, orphan, and mapping metrics.
- Weak-language detection is intentionally recall-heavy and can flag harmless prose.
- A chapter-only input can remove related context from elsewhere in the specification and should be used for testing only.
- Cached backend file paths stored by the browser stop working if outputs are moved, deleted, or generated on another server.
- Runtime filenames are timestamp-based. Concurrent runs in the same second may target the same filename.
- Downloads are resolved by basename across known output folders; identical basenames in different folders can be ambiguous.
- Version comparison works on extracted JSON, so extractor differences can look like source-specification changes and similarity matches still require engineering review.
- Inconsistency checking makes multiple full-document model calls and can be slow or expensive. Majority agreement reduces one-off findings but does not prove that a reported contradiction is real or that every contradiction was found.
- PDF extraction requires selectable text and uses rule-based heading, requirement, and table detection. Image-only PDFs, unusual layouts, and unconfigured normative wording can be missed.
- Extraction-quality scores are less authoritative without a source PDF or manually checked gold JSON. Empty expected/captured F1 sets score 100% by definition.
- The backend writes uploads and outputs locally and has no retention policy or authentication. It is suitable for local/research use, not an exposed production service.
- The frontend stores recent API responses in `localStorage`; it does not persist uploaded `File` objects across a page reload.
- Usage-cost estimates rely on a hard-coded price table and can become stale when model pricing changes.

## Checks

```bash
pytest
ruff check Backend tests
black --check Backend tests
cd Frontend
npm run lint
npm run build
```
