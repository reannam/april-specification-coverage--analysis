# Specification Coverage Analysis

AI-assisted tooling for extracting semiconductor specifications, generating requirement-linked verification plans (vPlans), and measuring specification-to-vPlan coverage.

The repository combines a Python/FastAPI backend with a React/TypeScript/Vite frontend. It supports:

- deterministic PDF-to-JSON extraction, including requirements, sections, tables, figures, notes, acronyms, cross-references, semantic chunks, and table CSVs;
- deterministic filtering of an extracted document to vPlan-relevant requirements;
- model-assisted requirement categorisation, edge-case extraction, vPlan generation, and test naming;
- deterministic weak-language checks and requirement-to-test traceability;
- deterministic and model-assisted coverage analysis;
- specification-version comparison;
- multi-reviewer internal-inconsistency checking for a source PDF;
- extraction-quality analysis against a source PDF and/or manually checked gold JSON;
- token-usage, estimated-cost, and trace metadata.

> This is a research and engineering-support tool. Its outputs are not verification sign-off artefacts and must be reviewed by a verification engineer.

For output schemas, metric formulae, interpretation guidance, and detailed limitations, see [USER_GUIDE.md](USER_GUIDE.md).

## End-to-end workflow

The main UI workflow is:

1. **Extract from PDF** — deterministically parse a selectable-text PDF into complete structured-document JSON and separate table CSVs.
2. **Extract requirements** — deterministically retain only requirements matching the configured normative, declarative, conditional, or feature-language patterns.
3. **Generate vPlan** — categorise requirements, detect weak language, extract relevant edge cases, generate test or traceability rows, add test categories and names, and export supporting reports.
4. **Check coverage** — re-evaluate the vPlan against the requirements, edge cases, and weak-language findings, then produce final coverage and gap reports.

The separate **Extract chapters** screen performs a client-side chapter filter for testing. Chapter-only inputs can remove related requirements from elsewhere in the specification and should not be treated as complete coverage inputs.

### vPlan generation sequence

1. Keep the top-level `requirements` array and write a preprocessed copy.
2. Use one whole-specification model call to create a controlled taxonomy of at most 12 parent categories, then assign every requirement to that fixed hierarchy in batches.
3. Run the deterministic weak-language checker.
4. Send flagged requirements to the edge-case model.
5. Generate vPlan rows in bounded parent-category batches, with related subcategories kept together.
6. Enrich executable rows with consistent test categories and concise test names. Existing usable categories and names are reused by default; model outputs are normalised and deterministic naming fallbacks are available.
7. Export requirement-to-test links, uncovered/partially covered information, usage records, and download metadata.

Every requirement should retain at least one traceability row. An `uncovered` row is not a proposed test: its name, description, steps, and expected results are cleared, while its constraint explains the missing information. A `partially_covered` row must still contain a real requirement-grounded action and observable expected result.

### Coverage sequence

Coverage requires four JSON inputs: requirements, vPlan, edge cases, and weak-language findings. It produces:

- verified requirement-level coverage statuses;
- requirement-mapping coverage;
- weighted full/partial coverage;
- traceability coverage;
- ambiguity-uncovered rate;
- orphan vPlan item rate;
- model-assisted granularity adequacy;
- deterministic and model-assisted testability details;
- a gap report, ambiguity report, coverage summary, and final coverage report.

The coverage workflow re-evaluates vPlan labels. When an initial vPlan label differs from the final coverage output, the final coverage output is authoritative within this tool.

## Model defaults

These values are taken from the current source code:

| Task | Default | Configuration |
| --- | --- | --- |
| Requirement taxonomy and assignment | `openai:gpt-5.6-terra` with reasoning disabled for schema-tool compatibility | `REQUIREMENT_CATEGORY_MODEL` |
| Edge-case extraction | `openai:gpt-5.4` | Fixed in code |
| vPlan generation | `openai:gpt-5.4` | Fixed in code |
| Test category and name enrichment | `openai:gpt-5.4-mini` | `CATEGORY_MODEL` |
| Coverage-status verification | Deterministic | No model |
| Granularity review | `openai:gpt-5.4` | `GRANULARITY_MODEL` |
| Testability review | `openai:gpt-5.4` | `TESTABILITY_MODEL` |
| Internal-inconsistency reviewers | `gpt-5.6-sol` | `INCONSISTENCY_MODEL` |

The OpenAI account behind `OPENAI_API_KEY` must have access to every configured model used by the selected workflow.

## Repository layout

```text
Backend/
  AnalyseAndCompareSpecs/   Specification comparison, inconsistency, and quality checks
  Coverage/                 Coverage workflow, metrics, and final reports
  Extraction/               Deterministic PDF and vPlan-relevant-content extraction
  vPlan/                    Agents, preprocessing, reporting, and post-processing
  api.py                    FastAPI application and routes
  config.py                 Runtime paths and shared configuration
  requirements.txt          Python dependencies used by the documented setup
Frontend/
  src/                      Current React application
  public/                   Static frontend assets
  package.json              Current frontend scripts and dependencies
tests/                      Backend unit tests
architecture-diagrams/      vPlan and coverage SVG architecture diagrams
outputs/                    Generated and historical output artefacts
uploads/                    Runtime upload cache and historical uploaded examples
old_input_files/            Older example inputs
helpers/                    Standalone duplicate-ID helper
USER_GUIDE.md               Detailed operating and interpretation guide
```

Architecture diagrams:

- [vPlan generation architecture](architecture-diagrams/vPlanArchitecture.drawio.svg)
- [coverage architecture](architecture-diagrams/coverage-flow.drawio.svg)

### Important layout note

The current runnable frontend is `Frontend/`. This repository snapshot also contains `Frontend/Frontend/`, an older duplicate that does not include the current internal-inconsistency page. Do not use the nested copy for local development.

The root `requirements.txt` currently duplicates `Backend/requirements.txt`; the commands below use the backend copy explicitly.

## Prerequisites

Use the versions configured by the repository's workflow:

- Python 3.12
- Node.js 20
- npm
- an OpenAI API key
- optional LangSmith credentials for tracing

No exact Python dependency versions are pinned in the current requirements file, so future fresh installations are not guaranteed to resolve the same package versions.

## Installation

Run all backend commands from the repository root.

### 1. Create the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r Backend/requirements.txt
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

### 2. Configure credentials

Create `.env` in the repository root:

```env
OPENAI_API_KEY=replace_me

# Optional LangSmith tracing
LANGSMITH_API_KEY=replace_me
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=specification-analysis
```

Do not commit `.env` or API keys.

For configuration overrides, exporting variables before starting Python is the reliable approach. `Backend/config.py` reads several values during import, before the application's later `load_dotenv()` calls.

```bash
export REQUIREMENT_CATEGORY_MODEL=openai:gpt-5.6-terra
export REQUIREMENT_CATEGORY_BATCH_SIZE=100
export REQUIREMENT_CATEGORY_BATCH_RETRIES=2

export CATEGORY_MODEL=openai:gpt-5.4-mini
export CATEGORY_BATCH_SIZE=24
export CATEGORY_MAX_WORKERS=2
export CATEGORY_BATCH_RETRIES=1
export REUSE_EXISTING_VPLAN_CATEGORIES=true

export VPLAN_CATEGORY_BATCH_SIZE=40
export VPLAN_BATCH_RETRIES=2

export COVERAGE_MODEL_BATCH_SIZE=10
export COVERAGE_MODEL_BATCH_RETRIES=2
export GRANULARITY_MODEL=openai:gpt-5.4
export TESTABILITY_MODEL=openai:gpt-5.4

export INCONSISTENCY_MODEL=gpt-5.6-sol
export INCONSISTENCY_AGENT_COUNT=6
export MAX_PRIORITY_SELECTIONS=12

export CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
export GENERATE_WORKFLOW_IMAGES=false
```

`GENERATE_WORKFLOW_IMAGES` is disabled by default because LangGraph's Mermaid PNG rendering may call a remote renderer.

### 3. Install the current frontend

```bash
cd Frontend
npm ci
cd ..
```

## Run locally

Start the backend from the repository root:

```bash
source .venv/bin/activate
uvicorn Backend.api:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal:

```bash
cd Frontend
npm run dev
```

Open:

- frontend: `http://localhost:5173`
- API: `http://localhost:8000`
- interactive API documentation: `http://localhost:8000/docs`

The frontend defaults to `http://localhost:8000`. To use another backend, set `VITE_API_BASE_URL` before starting Vite or place it in `Frontend/.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

If the frontend uses a different origin, export a matching comma-separated `CORS_ORIGINS` value before starting the backend.

## Input format

The vPlan workflow accepts a JSON object with a top-level `requirements` array. A raw top-level array is rejected by the API/preprocessor.

```json
{
  "requirements": [
    {
      "id": "REQ_I2C_001",
      "text": "The controller shall support 100 Kbps I2C operation.",
      "source_section": "1.1 I2C Features",
      "type": "functional_requirement"
    }
  ]
}
```

Each requirement should have a unique, non-empty `id` and non-empty `text`. Duplicate IDs are reported during coverage rather than rejected at upload time, but they make mapping and traceability unreliable. Additional extractor fields are retained where relevant.

The PDF extractor requires selectable text. Image-only/scanned PDFs are not OCRed by the implemented pipeline.

## API routes

| Method | Route | Main input |
| --- | --- | --- |
| `GET` | `/api/health` | None |
| `POST` | `/api/extract-pdf` | PDF field `source_pdf` |
| `POST` | `/api/extract-requirements` | JSON field `extracted_json` or cached form field `extracted_path` |
| `POST` | `/api/run-agents` | JSON field `requirements_file` |
| `POST` | `/api/run-coverage` | Requirements plus vPlan, edge-case, and weak-language JSON uploads or cached paths |
| `POST` | `/api/prioritise-vplan` | vPlan plus two JSON-array category selections |
| `POST` | `/api/compare-specifications` | JSON fields `old_specification` and `new_specification` |
| `POST` | `/api/check-inconsistencies` | PDF field `specification_pdf` |
| `POST` | `/api/check-specification-quality` | `extracted_json`, optional `source_pdf`, optional `gold_json`, and optional `threshold` |
| `GET` | `/api/download/{filename}` | Generated artefact basename |
| `GET` | `/api/usage-chart/{filename}` | Generated usage PNG or CSV basename |

The backend writes uploads and outputs to local directories. It has no authentication, database, retention policy, or production deployment configuration.

## Command-line workflows

Run vPlan generation from the repository root:

```bash
python -m Backend.vPlan.main path/to/requirements.json
```

Run coverage using four existing files:

```bash
python -m Backend.Coverage.coverage_workflow \
  --requirements-file path/to/requirements.json \
  --vplan-file path/to/vplan.json \
  --edge-case-file path/to/edge_cases.json \
  --weak-words-file path/to/weak_words.json
```

## Generated files

Runtime files are written below `uploads/` and `outputs/`. The main output subdirectories are configured in `Backend/config.py` and include:

- `outputs/extraction/` and `outputs/extraction/tables/`;
- `outputs/edge_cases/`;
- `outputs/weak_language/`;
- `outputs/traceability/`;
- `outputs/uncovered_tests/`;
- `outputs/prioritised_vplans/`;
- `outputs/coverage_status/`;
- `outputs/final_coverage_report/`;
- `outputs/analysis_and_comparison/`;
- `outputs/langsmith_logs/` and `outputs/usage_charts/`.

The final coverage directory uses stable filenames such as `coverage_summary.json`, `gap_report.json`, `ambiguity_report.json`, and `final_coverage_report.json`, so a later run overwrites those files. Other runtime filenames are commonly timestamp-based.

## Validation commands

From the repository root:

```bash
pytest -q
ruff check Backend tests
black --check Backend tests

cd Frontend
npm run lint
npm run build
```

The committed `.github/workflows/tests.yml` currently references older nested paths. Its backend job changes into `Backend/` and then refers to `Backend/requirements.txt` and root-level tests, while its frontend job tests `Frontend/Frontend/` instead of the current `Frontend/` application. Use the commands above locally and correct the workflow before treating CI as authoritative.

## Known limitations

- Model-assisted outputs are non-deterministic and can still be technically incorrect despite schemas, retries, and deterministic cleanup.
- Large specifications can be slow and costly. Batching reduces structured-output failures but does not remove model cost.
- The whole-specification taxonomy call is not batched and may become a context or cost bottleneck for very large inputs.
- Parent-category batches can separate requirements that are related across different categories, so supporting context may still be missed.
- Weak-language detection is intentionally recall-heavy and can flag harmless prose.
- Granularity and one testability review are model-assisted; most other coverage calculations are deterministic.
- Coverage depends on exact requirement IDs. Missing or duplicate IDs distort mapping, orphan, and traceability results.
- PDF extraction is rule-based. Scans, unusual layouts, unconfigured normative wording, and difficult tables or figures can be missed.
- Version comparison operates on extracted JSON, so extraction differences can appear as specification changes.
- Internal-inconsistency checking makes several full-document model calls and retains majority-agreed findings, but consensus does not prove correctness or completeness.
- Quality scores are less authoritative without the source PDF or a manually checked gold JSON.
- The frontend caches recent API responses in `localStorage`, but browser `File` objects are not persisted across reloads.
- Cached backend paths fail if files are moved, deleted, or were generated by another server instance.
- Download lookup uses basenames across known output folders and returns a conflict if the same basename exists in more than one folder.
- Usage-cost estimates use a hard-coded model price table and may become stale.
- Historical generated files and uploaded examples are present in this repository snapshot even though `outputs/` and `uploads/` are ignored for future untracked files.

## Contributors

| Contributor | Contribution |
| --- | --- |
| Reanna | vPlan generation and coverage analysis, UI |
| Jenna | Specification extraction and comparison |
| Elsa | Extraction of vPlan-relevant content only |
