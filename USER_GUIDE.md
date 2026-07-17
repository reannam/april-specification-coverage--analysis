# Specification Coverage Analysis — User Guide

This guide explains how to run the tool, how to interpret every main output, and how the coverage scores are calculated. It is written for both hardware verification engineers and software engineers supporting the workflow.

> **Engineering status:** the tool creates planning and review aids. It does not replace specification review, verification sign-off, simulation, formal verification, coverage closure, or engineering judgement.

## Contents

1. [What the tool does](#1-what-the-tool-does)
2. [Terminology](#2-terminology)
3. [End-to-end process](#3-end-to-end-process)
4. [Installation and startup](#4-installation-and-startup)
5. [Preparing the requirements JSON](#5-preparing-the-requirements-json)
6. [Using the interface](#6-using-the-interface)
7. [Which coverage result is authoritative](#7-which-coverage-result-is-authoritative)
8. [vPlan output](#8-vplan-output)
9. [Weak-language output](#9-weak-language-output)
10. [Edge-case output](#10-edge-case-output)
11. [Requirement-to-test links](#11-requirement-to-test-links)
12. [Uncovered-test report](#12-uncovered-test-report)
13. [Verified coverage-status output](#13-verified-coverage-status-output)
14. [Coverage scores and formulas](#14-coverage-scores-and-formulas)
15. [Final coverage files](#15-final-coverage-files)
16. [Usage and cost files](#16-usage-and-cost-files)
17. [Prioritised vPlan output](#17-prioritised-vplan-output)
18. [Specification extraction output](#18-specification-extraction-output)
19. [Specification comparison output](#19-specification-comparison-output)
20. [Extraction-quality output](#20-extraction-quality-output)
21. [Troubleshooting](#21-troubleshooting)
22. [Known limitations](#22-known-limitations)

## 1. What the tool does

The implemented workflow accepts structured requirements and produces:

- a verification plan (vPlan) linked to requirement IDs;
- a deterministic weak-language report;
- model-assisted edge-case candidates;
- a requirement-to-vPlan traceability CSV;
- an uncovered and partially covered report;
- requirement-level verified coverage statuses;
- several coverage scores and supporting records;
- gap and ambiguity reports;
- token-usage and estimated-cost records.
- version-to-version specification comparison reports;
- extraction completeness, accuracy, and table/figure capture scores.
- deterministic PDF extraction and vPlan-ready requirements JSON.

The workflow is deliberately conservative. It should downgrade questionable evidence rather than label a requirement fully covered without enough support.

PDF and requirement extraction are implemented under **Prepare**. Comparison and extraction-quality analysis are implemented under **Analyse and compare**.

## 2. Terminology

| Term | Meaning in this tool |
| --- | --- |
| Specification requirement | One object in the input `requirements` array. |
| vPlan row | One record linked to one source requirement. It may be an executable test or an uncovered traceability row. |
| Executable test | A vPlan row with a specific description, at least one executable step, and at least one observable expected result. |
| Traceability row | A record preserving the link to a requirement even when no responsible test can be generated. |
| Covered | The available evidence supports a complete, executable verification intent. |
| Partially covered | At least one reasonable test is possible, but some behaviour or evidence remains incomplete. |
| Uncovered | The supplied material does not support a responsible executable test. |
| Ambiguous / not yet plannable | A final coverage status used when no complete test is available and linked ambiguity evidence exists. It scores the same as uncovered. |
| Edge case | A boundary, optional, conditional, timing, ordering, or implementation-dependent situation implied by a requirement. |
| Weak-language flag | A deterministic wording warning. It is evidence for review, not proof that the requirement is wrong. |
| Orphan vPlan item | A vPlan row whose trace information cannot be matched to the supplied specification content. |

## 3. End-to-end process

1. **Extract from PDF** creates the complete structured specification. This stage does not select a vPlan input.
2. **Extract requirements** refines that document to the relevant requirements JSON and selects it for the next stage.
3. The refined JSON is validated and copied into the vPlan upload area.
4. Preprocessing retains the `requirements` array used by the agents.
5. GPT-5.6 Terra reads the complete refined requirement set and defines one controlled hierarchy of up to 12 broad requirement categories and their subcategories.
6. Smaller assignment batches classify every requirement using that fixed hierarchy; they cannot invent additional labels.
7. The weak-language checker scans the requirement text using configured word and phrase lists.
8. The edge-case agent reviews flagged requirements and produces only relevant edge-case candidates.
9. The vPlan generator gathers requirements from all chapters by parent category, keeps subcategories contiguous, and applies a size cap to oversized groups.
10. Structured-output validation enforces the vPlan schema.
11. Uncovered rows are cleared of test names, descriptions, steps, and expected results.
12. A GPT-5.4-mini enrichment pass assigns test-level categories and test names only to executable rows. Deterministic cleanup and fallbacks are applied.
13. Traceability and uncovered-test reports are exported.
14. Coverage analysis re-evaluates the vPlan against the refined requirements, weak-language flags, and edge cases. Its model-assisted checks run in visible, retried batches.
15. Final coverage summaries, detailed reports, usage records, and download links are produced.

The vPlan generator uses the model’s judgement, but important output-shape rules are also enforced in code. This prevents an uncovered row from retaining speculative test content even if the model returns it.

## 4. Installation and startup

### Backend

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r Backend/requirements.txt
```

Existing environments created before PDF extraction was added must be refreshed.
If startup or extraction reports that `fitz` or `pymupdf` is missing, activate
the environment used by `uvicorn` and run:

```bash
python -m pip install pymupdf
```

Create `.env` in the repository root:

```env
OPENAI_API_KEY=replace_me

# Optional tracing
LANGSMITH_API_KEY=replace_me
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=specification-analysis

# Optional model and batching settings
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
GRANULARITY_MODEL=openai:gpt-5.4
TESTABILITY_MODEL=openai:gpt-5.4
```

Start the API:

```bash
uvicorn Backend.api:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

In a second terminal:

```bash
cd Frontend
npm install
npm run dev
```

The default addresses are:

- frontend: `http://localhost:5173`;
- backend: `http://localhost:8000`;
- health check: `http://localhost:8000/api/health`.

Use `VITE_API_BASE_URL` if the API is hosted elsewhere. The allowed CORS origins in `Backend/api.py` must include the frontend origin.

## 5. Preparing the requirements JSON

The normal input is a JSON object containing a top-level `requirements` array:

```json
{
  "requirements": [
    {
      "id": "REQ_I2C_001",
      "description": "Normal-mode transfer support.",
      "text": "The controller shall support 100 Kbps I2C operation.",
      "source_section": "1.1 I2C Features",
      "signals": ["scl", "sda"],
      "type": "functional_requirement"
    }
  ]
}
```

### Input values

| Value | Required | Meaning and effect |
| --- | --- | --- |
| `requirements` | Yes | Array of requirement objects processed by the workflow. |
| `id` | Effectively yes | Stable, unique requirement identifier. It is the primary traceability key. Missing or duplicate IDs make coverage unreliable. |
| `text` | Strongly recommended | Original normative or descriptive wording. It is the main source for tests and coverage review. |
| `description` | Recommended | Additional requirement wording. The weak-language checker combines it with `text` when both are present. |
| `source_section` | Recommended | Human-readable source location. It improves review and traceability. |
| `signals` | Optional | Signals explicitly associated with the requirement. They may support more specific tests but are never assumed if absent. |
| `type` | Optional | Requirement classification, such as `functional_requirement` or `register_requirement`. |
| Other values | Optional | Preserved where the workflow copies the source requirement. They are not automatically given special meaning. |

### Input rules

- Every `id` should be non-empty and unique.
- Preserve exact requirement wording.
- Do not insert implementation assumptions merely to make the generator produce tests.
- Include units, legal values, timing, reset conditions, configuration dependencies, and observable outcomes when the source genuinely defines them.
- A chapter-only extract can remove related definitions elsewhere in the specification. Use chapter extraction for testing, not final coverage claims.

## 6. Using the interface

### Extract a PDF

1. Open **Extract from PDF** under **Prepare**.
2. Upload a text-based specification PDF.
3. Select **Extract specification** and follow page progress in the backend terminal.
4. Review the extraction counts and searchable requirement records.
5. Download the complete document JSON for archival, comparison, and quality checking if required.
6. Continue to **Extract requirements**. PDF extraction does not select a vPlan input.

The extractor is deterministic and does not make model calls. It uses PDF layout, heading rules, and configured engineering-language regular expressions. Scanned or image-only PDFs require OCR before this workflow.

### Extract requirements from existing document JSON

1. Open **Extract requirements** under **Prepare**.
2. Upload a complete extracted document JSON containing a top-level `requirements` array.
3. Select **Extract requirements**.
4. Review and download the compact result.
5. Continue to **Generate vPlan**; this refined file is the first extraction output selected as a vPlan input.

This operation validates that every requirement is an object with non-empty `text`. It preserves the engineering fields already present; it does not invent missing IDs, wording, signals, sections, or pages.

### Generate a vPlan

1. Open **Generate vPlan**.
2. Upload the requirements JSON.
3. Start the workflow.
4. Wait for vPlan, edge-case, and weak-language outputs.
5. Review each output in its dedicated page or download the original file.

For large inputs, the backend first derives one whole-specification taxonomy, then assigns requirements to it in bounded batches. vPlan generation gathers same-parent requirements across chapters; subcategories keep the closest material together before oversized categories are split. The terminal prints the start, completion, retry, or failure of every categorisation and vPlan batch. A malformed vPlan response is retried according to `VPLAN_BATCH_RETRIES`. A failed vPlan run does not currently resume from the last successful batch.

### Check coverage

1. Open **Check coverage**.
2. Reuse the latest cached files or upload all four inputs manually:
   - requirements JSON;
   - vPlan JSON;
   - edge-case JSON;
   - weak-language JSON.
3. Select **Run coverage checks**.
4. Click any score or count to open its supporting records.
5. Download the final coverage files for review and retention.

Do not mix files from unrelated runs. Requirement IDs can match accidentally across projects and create misleading mappings.

### Prioritise a vPlan

The optional priority function shows subcategories grouped beneath their parent requirement categories. Select between 2 and `MAX_PRIORITY_SELECTIONS` areas across Priority 1 and Priority 2, including at least one Priority 1 selection. The default maximum is 12. This is user-controlled ordering and does not calculate engineering criticality.

### Compare specification versions

1. Open **Compare specification versions** under **Analyse and compare**.
2. Upload the older extractor `document.json` first and the newer version second.
3. Select **Compare versions**.
4. Review headline counts, then expand each review area and category.
5. Download JSON for automation, CSV for filtering, or Markdown for human review.

The comparator analyses extracted JSON structure and content. It does not compare two PDFs directly.

### Quality checker

1. Open **Quality checker** under **Analyse and compare** and upload the extractor `document.json`.
2. Optionally add the source PDF. Without it, PDF-fidelity and capture evidence is unavailable.
3. Optionally add a manually checked gold JSON. This changes the accuracy formula to use reference F1 values.
4. Set the pass threshold from 0 to 100 percent; the default is 95 percent.
5. Select **Check quality**, inspect every component, and download the report JSON.

## 7. Which coverage result is authoritative

The coverage label inside each vPlan row is an **initial planning judgement** produced during generation. It helps later analysis, but it is not the final answer.

The statuses and scores in the following coverage outputs are more relevant and final:

1. `coverage_summary.json` for headline counts and percentages;
2. `final_coverage_report.json` for the same final values plus supporting metrics;
3. the verified coverage-status JSON for requirement-by-requirement decisions;
4. `gap_report.json` and `ambiguity_report.json` for investigation.

If the vPlan says `covered` but the verified coverage file says `Partially covered` or `Uncovered`, use the verified coverage result. The final verifier checks the actual test content and linked ambiguity evidence; it does not accept the original label on trust.

### Strict final status rules

- **Covered:** every linked row has a non-empty, requirement-grounded description, at least one executable step, at least one observable expected result, a recognised `covered` label, and no linked ambiguity evidence.
- **Partially covered:** at least one complete test exists, but some row, label, behaviour, or ambiguity evidence prevents full confidence.
- **Uncovered:** there is no complete executable test.
- **Ambiguous / not yet plannable:** there is no complete executable test and linked weak-language or edge-case evidence exists.

When evidence is mixed or borderline, the process is designed to downgrade rather than overstate coverage.

The model-assisted granularity and testability checks receive the full text of a related requirement only when a linked vPlan row explicitly cites its ID in `supporting_requirement_ids`. Their prompts allow that text to improve an assessment only when it directly supplies a missing value, condition, signal, outcome, or rule. Merely sharing a category or discussing a similar behaviour is not enough. Missing or uncited IDs are not supplied to the reviewers. Coverage detail records expose the resolved supporting requirements so engineers can audit the decision.

Granularity and model-assisted testability use batches of 10 requirements by default. Every returned assessment must acknowledge every linked `test_id`; otherwise that batch is retried and ultimately marked `unclear`. The `vplan_item_audit` block records the total vPlan rows, submitted row count, submitted IDs, failed requirement IDs, and whether API quota was exhausted. `not_mapped` is determined from actual ID linkage and cannot be asserted by the model when linked rows exist. If account quota is exhausted, further model calls stop immediately while deterministic coverage calculations continue; reducing batch size does not restore exhausted account quota.

## 8. vPlan output

### Categorised-requirements intermediate file

Typical filename: `<source>_requirements_only_categorised.json` in `uploads/preprocessed`.

This intermediate file exists so the exact hierarchy used for batching is auditable and reusable throughout the run. It contains the original requirement objects plus `requirement_category` and `requirement_subcategory`. Its `metadata` records `requirement_category_model`, the complete `taxonomy`, `assignment_batch_size`, `number_of_assignment_batches`, and `failed_assignment_batches`. A failed batch number means those requirements were retained as `Uncategorised`; it must not be interpreted as a successful classification. This is a processing artefact, not a coverage report.

Typical filename: `generated_vplan_<timestamp>.json`.

### Why this file exists

The vPlan is the main verification-planning artefact. It connects source requirements to proposed executable tests while retaining traceability rows for requirements that cannot yet support a responsible test.

### Top-level values

| Value | Meaning |
| --- | --- |
| `metadata` | Information about the run and source file. |
| `feature_list` | Array of vPlan rows. |

### `metadata` values

| Value | Meaning |
| --- | --- |
| `requirements_file` | Source requirements filename. |
| `date_created` | Human-readable generation date. |
| `time_created` | Human-readable generation time. |
| `number_of_requirements` | Number of input requirement objects. |
| `number_of_tests` | Number of vPlan rows. This includes uncovered traceability rows, so it is not necessarily the number of executable tests. |
| `batching_strategy` | Strategy used to gather requirements. `requirement_category_with_size_cap` means whole-spec parent categories are grouped before oversized groups are split. |
| `max_category_batch_size` | Maximum requirements supplied to one vPlan generation call. |
| `number_of_batches` | Number of vPlan generation batches. |
| `batch_categories` | Parent requirement category used for each generation batch. A repeated value means that category exceeded the size cap. |
| `number_of_edge_case_candidates` | Edge-case candidates made available to vPlan generation. |
| `langsmith_trace_id` | Parent run identifier used for tracing. It is not a coverage value. |
| `batch_trace_ids` | Trace identifiers for individual vPlan batches. |
| `specification_name` | Human-readable name inferred from source metadata or filename. |
| `section` | Common source section when it can be determined; otherwise `null`. |
| `display_name` | Human-readable vPlan title used by the interface. |
| `requirements_file_path` | Backend path to the source requirements file. Paths are local to that backend instance. |

### Every `feature_list` row

| Value | Allowed values / type | Meaning |
| --- | --- | --- |
| `test_id` | String | Unique vPlan-row identifier. It remains present for uncovered traceability rows. |
| `test_name` | String | Concise name derived from `test_description`. It is empty for uncovered rows. |
| `requirement_id` | String | Exact source requirement ID used for mapping. |
| `requirement_category` | String | Broad parent category assigned from the controlled whole-spec taxonomy before generation. |
| `requirement_subcategory` | String | Finer taxonomy label nested beneath `requirement_category`. |
| `supporting_requirement_ids` | Array of strings | Other requirements in the same category batch whose explicit wording was used to complete this row. IDs are restricted to the batch; the link remains model-assessed and requires review. |
| `requirement_text` | String | Source wording copied deterministically after generation. |
| `scenario_type` | `nominal`, `illegal`, `corner` | Nature of the scenario, not its coverage status. `nominal` is valid/expected behaviour; `illegal` is forbidden or erroneous behaviour; `corner` is a legal edge or boundary. |
| `category` | String | Short engineering category assigned during enrichment. Uncovered rows use `Uncategorised`. |
| `priority` | `1`, `2`, `3` | User/category-based ordering where 1 is highest. Default is 3. It is not a generated safety, risk, or criticality claim. |
| `test_description` | String | Specific behaviour the row verifies. Empty for uncovered rows. |
| `test_constraints` | String | Conditions supported by the requirement and, for uncovered rows, the reason or clarification needed. It must not silently add missing technical facts. |
| `test_steps` | Array of strings | One to three concise executable actions. Empty for uncovered rows. |
| `expected_results` | Array of strings | One or two observable pass/fail outcomes. Empty for uncovered rows. |
| `coverage` | `covered`, `partially_covered`, `uncovered` | Initial vPlan judgement. Coverage files later re-evaluate it and are authoritative. |

### vPlan coverage meanings

| Value | Meaning |
| --- | --- |
| `covered` | The row appears directly testable from the supplied material. It still needs final verification. |
| `partially_covered` | At least one real test action and outcome are supported, but some relevant information remains incomplete. |
| `uncovered` | No responsible executable test can be generated. `test_name`, `test_description`, `test_steps`, and `expected_results` are always empty. `test_constraints` should explain what is missing. |

## 9. Weak-language output

Typical filename: `weak_words_<timestamp>.json` in `outputs/weak_language`.

### Why this file exists

This deterministic report identifies wording that may make a requirement optional, ambiguous, or insufficiently normative. Coverage analysis uses it as cautionary evidence.

### Top-level values

| Value | Meaning |
| --- | --- |
| `number_of_language_issues` | Total issue records. One requirement can produce more than one issue. |
| `source_file` | Source requirements filename. |
| `issues` | Array of wording issues. |

### Every issue

| Value | Meaning |
| --- | --- |
| `requirement_id` | Requirement being flagged. |
| `requirement_text` | Exact combined `text`/`description` used for review. |
| `source_section` | Source location, or a value derived from the requirement ID when possible. |
| `issue_type` | `weak_or_optional_language` or `missing_strong_requirement_language`. |
| `matched_words` | Exact configured weak terms found. Empty for a missing-strong-language issue. |
| `message` | Explanation of why the wording deserves review. |

A flag is not proof of a defect. Descriptive prose, headings, permissions, and deliberately optional behaviour can be valid.

## 10. Edge-case output

Typical filename: `generated_edge_case_info_<timestamp>.json`.

### Why this file exists

The edge-case report converts relevant ambiguous or conditional wording into concrete review concerns that may affect verification planning. It helps prevent a vPlan from treating uncertain behaviour as fully defined.

### `metadata` values

| Value | Meaning |
| --- | --- |
| `requirements_file` | Backend path to the processed requirements file. |
| `requirements_filename` | Clean source filename. |
| `weak_language_file` | Weak-language report used by the edge-case stage. |
| `date_created`, `time_created` | Creation date and time. |
| `total_requirements` | Requirements reviewed by the workflow. |
| `number_of_weak_language_instances` | Total weak-language issue records. |
| `number_of_flagged_requirements` | Unique/selected requirements passed to edge-case analysis. |
| `number_of_edge_case_candidates` | Edge-case records returned. |
| `langsmith_trace_id` | Trace identifier for the model call. |

### Every `edge_cases` record

| Value | Meaning |
| --- | --- |
| `edge_case_id` | Unique edge-case identifier. |
| `requirement_id` | Exact linked requirement ID. |
| `edge_case_type` | One of `optional_behaviour`, `conditional_behaviour`, `ambiguous_expected_result`, `unclear_mandatory_status`, `implementation_dependent`, `timing_or_ordering_edge_case`, or `boundary_condition`. |
| `edge_case_description` | Concise statement of the requirement-specific verification concern. |
| `requirement_text` | Source wording added after model generation. |
| `source_section` | Source section added after model generation. |

## 11. Requirement-to-test links

Typical filename: `<vplan-name>_requirement_test_links.csv`.

### Why this file exists

This compact CSV supports traceability review and import into other engineering tools. It answers: “Which vPlan row IDs are linked to each requirement ID?”

| Column | Meaning |
| --- | --- |
| `requirement_id` | Source requirement identifier. |
| `related_tests` | JSON text containing `{"test_ids": [...], "supporting_requirement_ids": [...]}`. Test IDs include uncovered traceability rows; supporting IDs record other source requirements cited by linked tests. |

This file proves a link exists; it does not prove the linked row is complete or correct.

## 12. Uncovered-test report

Typical filename: `uncovered_test_report_<timestamp>.json`.

### Why this file exists

This report isolates rows needing clarification or additional specification detail, so engineers do not have to search the entire vPlan.

### `metadata` values

| Value | Meaning |
| --- | --- |
| `vplan_file` | vPlan used to build the report. |
| `edge_case_file` | Edge-case report used for context. |
| `date_created`, `time_created` | Creation date and time. |
| `number_of_uncovered_tests` | Count of uncovered traceability rows. |
| `number_of_partially_covered_tests` | Count of partially covered executable rows. |

### `uncovered_tests` and `partially_covered_tests` values

| Value | Meaning |
| --- | --- |
| `test_id` | vPlan-row identifier. |
| `requirement_id` | Linked requirement. |
| `coverage` | `uncovered` or `partially_covered`. |
| `test_description` | Empty for uncovered rows; supported test intent for partial rows. |
| `reason` | The vPlan `test_constraints` value. For uncovered rows this should explain missing information. |
| `required_clarification` | Deterministically inferred category of clarification required. It is guidance, not a specification fact. |
| `related_edge_cases` | Relevant edge-case IDs, types, and descriptions. |

## 13. Verified coverage-status output

Typical filename: `verified_coverage_status_example.json`.

### Why this file exists

This is the requirement-by-requirement re-evaluation that separates final coverage judgement from the vPlan generator’s initial labels.

### `metadata` values

| Value | Meaning |
| --- | --- |
| `date_created`, `time_created` | Creation date and time. |
| `number_of_requirements` | Requirements assessed. |
| `number_of_vplan_tests` | Number of vPlan rows, including uncovered traceability rows. |
| `status_counts` | Count for each final status string. |

### Every `labelled_requirements` record

The original requirement values are copied first. The following values are added:

| Value | Meaning |
| --- | --- |
| `verified_coverage_status` | Final requirement status: `Covered`, `Partially covered`, `Uncovered`, or `Ambiguous / not yet plannable`. |
| `coverage_verification_reason` | Deterministic explanation of the evidence and downgrade decision. |
| `original_vplan_coverage_values` | Recognised initial labels from linked vPlan rows. These are retained for comparison, not treated as final. |
| `linked_tests` | Linked vPlan `test_id` values. |
| `linked_edge_cases` | Full edge-case records linked by requirement ID. |
| `linked_weak_word_flags` | Full weak-language issue records linked by requirement ID. |

### Every `traceability` record

| Value | Meaning |
| --- | --- |
| `requirement_id` | Source requirement ID. |
| `linked_test_ids` | Linked vPlan-row IDs. |
| `original_vplan_coverage_values` | Initial labels from those rows. |
| `verified_coverage_status` | Final requirement-level decision. |
| `has_edge_case_flags` | Whether edge-case evidence is linked. |
| `has_weak_word_flags` | Whether weak-language evidence is linked. |

### Every `uncovered_test_report` record

| Value | Meaning |
| --- | --- |
| `requirement_id` | Requirement that is uncovered or ambiguous/not yet plannable. |
| `uncovered_reason` | Final reason no complete test is available. |
| `linked_tests` | Any linked traceability or test rows. |
| `original_vplan_coverage_values` | Initial vPlan labels. |
| `edge_cases` | Linked edge-case evidence. |
| `weak_word_flags` | Linked wording evidence. |

## 14. Coverage scores and formulas

All percentages are rounded to two decimal places. A high percentage only describes the formula named; it is not an overall proof of verification completeness.

### 14.1 Requirement mapping coverage

**Purpose:** measures whether each specification requirement ID appears in at least one vPlan row.

`requirement_mapping_coverage = mapped specification items / total specification items × 100`

Important: an uncovered traceability row counts as mapped. Therefore, 100% mapping can coexist with low weighted or testability coverage.

Supporting values:

| Value | Meaning |
| --- | --- |
| `metric_name` | `Requirement Mapping Coverage`. |
| `total_spec_items` | Number of source requirements. |
| `spec_items_mapped_to_vplan` | Requirements whose IDs appear in the vPlan. |
| `spec_items_unmapped_to_vplan` | Requirements with no matching vPlan row. |
| `requirement_mapping_coverage` | Calculated percentage. |
| `mapped_requirement_ids` | IDs counted as mapped. |
| `unmapped_requirement_ids` | IDs counted as unmapped. |

### 14.2 Weighted coverage

**Purpose:** distinguishes fully, partially, and non-covered requirements without unsupported criticality or importance values.

Each final requirement status receives:

- Covered = `1.0`;
- Partially covered = `0.5`;
- Uncovered = `0.0`;
- Ambiguous / not yet plannable = `0.0`.

`weighted_coverage = sum(coverage scores) / total requirements × 100`

This is “weighted” only by coverage state. Requirements are **not** assigned importance, safety, or criticality weights.

Supporting values:

| Value | Meaning |
| --- | --- |
| `formula` | Machine-readable explanation of the calculation. |
| `total_items` | Requirements included in the denominator. |
| `weighted_score` | Sum of 1.0, 0.5, and 0.0 values before conversion to a percentage. |
| `weighted_coverage` | Final percentage. |
| `rows` | Requirement ID, final status, and `coverage_score` used for each item. |

### 14.3 Traceability coverage

**Purpose:** measures whether vPlan rows contain a recognised source reference.

`traceability_coverage = vPlan items with source trace / total vPlan items × 100`

Recognised traces include requirement IDs, source sections, table/figure/rule IDs, page references, and explicit traceability values.

Supporting values include `total_vplan_items`, `vplan_items_with_source_trace`, `vplan_items_without_source_trace`, `traceable_items`, and `untraceable_items`.

Traceability does not establish that a test is technically adequate.

### 14.4 Testability coverage

**Headline/final purpose:** measures how many mapped requirements have a final status that indicates at least some executable test evidence.

`testability_coverage = mapped items with testable vPlan entry / mapped specification items × 100`

For the headline final score:

- Covered and Partially covered count as testable;
- Uncovered and Ambiguous / not yet plannable do not;
- requirements with no linked vPlan row are outside the mapped-item denominator.

The workflow also returns a separate `model_testability` diagnostic with labels `fully_testable`, `partially_testable`, `not_testable`, `not_mapped`, and `unclear`. It is useful for review but is not the headline final score displayed by the coverage page.

### 14.5 Granularity adequacy

**Purpose:** measures whether mapped requirements are addressed at suitably specific behavioural detail.

`granularity_adequacy = requirements covered at suitable detail / mapped requirements × 100`

This is model-assisted. Assessment values are:

| Value | Meaning |
| --- | --- |
| `requirement_id` | Requirement assessed. |
| `suitable_detail` | Boolean result. |
| `granularity_label` | `suitable_detail`, `too_broad`, `not_mapped`, or `unclear`. |
| `reason` | Explanation of the judgement. |
| `linked_tests` | Test IDs considered. |

An uncovered or structurally incomplete row cannot count as suitable detail.

### 14.6 Orphan vPlan item rate

**Purpose:** identifies vPlan rows that cannot be traced to supplied specification content.

`orphan_rate = orphan vPlan items / total vPlan items × 100`

For this metric, lower is better.

Supporting values include `vplan_items_with_source_in_spec`, `orphan_vplan_items`, `linked_items`, and `orphan_items`. Each item includes its test ID, available trace values, and description.

### 14.7 Ambiguity-related uncovered rate

**Purpose:** shows how much of the specification remains uncovered with linked ambiguity evidence.

`ambiguity_uncovered_rate = specification items uncovered due to ambiguity / total specification items × 100`

For this metric, lower is better. Supporting values include:

| Value | Meaning |
| --- | --- |
| `spec_items_uncovered_due_to_ambiguity` | Count in the numerator. |
| `other_spec_items` | Remaining specification items. |
| `ambiguity_uncovered_rate` | Calculated percentage. |
| `ambiguity_uncovered_requirements` | Detailed evidence records. |

## 15. Final coverage files

### `coverage_summary.json`

**Why it exists:** compact, authoritative headline output for dashboards, reporting, and quick review.

| Section/value | Meaning |
| --- | --- |
| `metadata` | Source filenames and creation information. |
| `coverage_summary.total_spec_items` | Requirements in scope. |
| `coverage_summary.covered` | Final Covered count. |
| `coverage_summary.partially_covered` | Final Partially covered count. |
| `coverage_summary.uncovered` | Final Uncovered count. |
| `coverage_summary.ambiguity_uncovered` | Final Ambiguous / not yet plannable count. |
| `coverage_summary.orphan_vplan_items` | Orphan row count. |
| `coverage_summary.granularity_mapped_requirements` | Requirements included in the granularity denominator. |
| `coverage_summary.granularity_suitable_detail` | Requirements judged suitably detailed. |
| `coverage_summary.granularity_not_mapped` | Requirements with no vPlan mapping in the granularity assessment. |
| `coverage_percentages` | Final headline metric values described in Section 14. |

### `gap_report.json`

**Why it exists:** review queue of every requirement whose final status is not Covered.

Each `gap_report` record contains:

- `requirement_id`;
- `source_section`;
- `coverage_status`;
- `spec_statement`;
- `linked_vplan_items`;
- `reason`.

The report intentionally contains no unsupported ranking, criticality, or importance values. Records remain in source evaluation order.

### `ambiguity_report.json`

**Why it exists:** focused evidence for requirements with ambiguity status, edge cases, or weak-language flags.

Each record contains `requirement_id`, `source_section`, `coverage_status`, `spec_statement`, `linked_tests`, `reason`, `linked_edge_cases`, and `linked_weak_word_flags`.

### `granularity_adequacy_<timestamp>.json`

**Why it exists:** preserves the model-assisted granularity assessment and its supporting records separately from deterministic scores.

Top-level values are `metric_name`, `definition`, `formula`, counts, `granularity_adequacy`, `label_counts`, `assessments`, and `usage`.

### `final_coverage_report.json`

**Why it exists:** complete final package for audit and detailed engineering review.

It combines:

- `metadata`;
- `coverage_summary`;
- `coverage_percentages`;
- `gap_report`;
- `ambiguity_report`;
- `supporting_metrics.requirement_mapping`;
- `supporting_metrics.weighted_coverage`;
- `supporting_metrics.traceability`;
- `supporting_metrics.testability`;
- `supporting_metrics.orphan_rate`;
- `granularity_adequacy` when available;
- `ambiguity_uncovered` when available.

This is the best single file to retain when a full machine-readable result is needed.

## 16. Usage and cost files

### Per-run usage log

Typical filename: `<output-name>_usage_log.json`.

**Why it exists:** records model usage, trace IDs, and estimated cost for reproducibility and experiment monitoring.

| Value | Meaning |
| --- | --- |
| `timestamp` | Run time in ISO format. |
| `output_file` | Output associated with the usage record. |
| `trace_ids` | Available tracing IDs by workflow stage. |
| `summary.prompt_tokens` / `input_tokens` | Model input-token count. Duplicate naming supports different callback conventions. |
| `summary.completion_tokens` / `output_tokens` | Model output-token count. |
| `summary.total_tokens` | Total tokens reported. |
| `summary.total_cost` | Estimated USD cost. |
| `summary.agents` | Per-agent usage records. |
| `agent_name` | Workflow stage. |
| `model_name` | Model used. |

### `all_usage_runs.json`

**Why it exists:** append-only local history used to create cross-run charts and CSV files.

### Usage CSVs

- `usage_by_run.csv`: one row per saved run;
- `usage_by_agent.csv`: one row per agent/stage per run.

Columns include run ID, timestamp, output file, model/agent name, token counts, and estimated cost.

### Usage PNG charts

- `estimated_cost_by_run.png`;
- `total_tokens_by_run.png`;
- `estimated_cost_by_agent.png`;
- `tokens_by_agent.png`.

Cost values are estimates based on the local price table, not billing records.

## 17. Prioritised vPlan output

Typical filename: `prioritised_vplan_<timestamp>.json`.

### Why this file exists

It provides a user-controlled working order based on chosen requirement subcategories grouped beneath major categories. The underlying tests are not regenerated.

Additional metadata values:

| Value | Meaning |
| --- | --- |
| `prioritised` | `true` after priorities are applied. |
| `priority_1_categories` | Hierarchical category/subcategory selectors chosen for priority 1. |
| `priority_2_categories` | Hierarchical category/subcategory selectors chosen for priority 2. |
| `prioritised_at` | ISO timestamp. |

Any unselected category receives priority 3. Priority is a workflow choice, not a model-derived safety assessment.

## 18. Specification extraction output

PDF extraction creates a complete document file named `<run>_document.json` and zero or more table CSV files under `outputs/extraction`. The separate **Extract requirements** stage creates `<document>_requirements.json` from that complete document.

### Why these files exist

- **Complete document JSON** preserves page text, structure, tables, notes, acronyms, references, and semantic chunks. It is the input for specification comparison and the quality checker.
- **Requirements JSON** is produced only by the next workflow stage. It contains document identity and relevant extracted requirement records, and is the direct input to vPlan generation.
- **Table CSV files** preserve cells detected by PyMuPDF for separate review and support the table records referenced by the complete document.

### Complete document top-level values

| Value | Meaning |
| --- | --- |
| `document_name` | Original uploaded PDF filename shown to users. Runtime UUIDs are not used as document identity. |
| `metadata` | PDF metadata supplied by the source file. Missing metadata remains `null`; it is not inferred. |
| `total_pages` | Number of pages opened from the PDF. |
| `sections` | Flat section records derived from recognised headings and their numeric hierarchy. |
| `requirements` | De-duplicated normative or behavioural statements detected in page text and tables. |
| `tables` | Detected table records with source page and generated CSV path. |
| `notes` | Lines beginning with configured note labels such as NOTE, WARNING, or CAUTION. |
| `acronyms` | De-duplicated uppercase tokens after the common-word stop list is applied. |
| `cross_references` | Detected section and table references. |
| `semantic_chunks` | Consecutive page text grouped under the most recently detected section. |
| `pages` | Per-page source text, headings, table captions, and table records. |

### Requirement-record values

| Value | Meaning |
| --- | --- |
| `id` | Deterministic `REQ_<section>_<sequence>` identifier assigned after de-duplication. It is unique within that extraction run. |
| `text` | Extracted normative or behavioural wording used by downstream agents. It must be reviewed against the PDF. |
| `source_section` | Most recent recognised section heading when the requirement was found; `Unknown` when no valid heading has been seen. |
| `source_page` | One-based PDF page number on which the requirement was detected. |
| `signals` | Uppercase signal-like tokens detected in the requirement text. This is lexical detection, not design connectivity. |
| `type` | Extraction-rule origin such as `protocol_rule`, `encoding_rule`, or `table_requirement`. It is not severity or coverage. |

### Requirements-refinement output values

| Value | Meaning |
| --- | --- |
| `document_name` | Source document identity carried forward from the complete extraction. |
| `refinement_summary.input_requirements` | Candidate requirement records supplied by the complete document. |
| `refinement_summary.vplan_relevant_requirements` | Records retained after normative and behavioural relevance rules are reapplied. |
| `refinement_summary.excluded_requirements` | Candidate records excluded as descriptive, illustrative, or otherwise unsupported by the configured vPlan relevance rules. |
| `requirements` | The retained requirement records and the only content passed into vPlan preprocessing. |

### Other nested values

| Value | Meaning |
| --- | --- |
| `metadata.title`, `author`, `subject`, `keywords`, `creator`, `producer` | Optional PDF metadata strings. |
| `metadata.creation_date`, `modification_date` | PDF metadata date strings in the source format. They are not normalised timestamps. |
| `sections[].id` | Recognised numeric or appendix-style section identifier. |
| `sections[].title` | Heading text following the section identifier. |
| `sections[].parent` | Identifier before the final dot, or `null` for a top-level section. |
| `tables[].page` | One-based page containing the table. |
| `tables[].csv_file` | Backend-local path to the extracted table CSV. |
| `notes[].type` | Detected note prefix. |
| `notes[].text` | Complete captured note line. |
| `semantic_chunks[].section` | Section assigned to the accumulated text. |
| `semantic_chunks[].text` | Extracted text accumulated while that section was current. |
| `pages[].page_number` | One-based PDF page number. |
| `pages[].text` | Raw text extracted by PyMuPDF for that page. |
| `pages[].headings` | Heading records detected on that page. |
| `pages[].table_captions` | Lines matching the configured table-caption rule. |
| `pages[].tables` | Tables detected on that page. |

The extraction summary shown in the interface contains counts of these arrays. These are extraction counts, not quality, risk, or coverage scores.

## 19. Specification comparison output

Typical filenames are `version_differences_<timestamp>.json`, `.csv`, and `.md`.

### Why these files exist

- **JSON** is the complete machine-readable record used by the UI and downstream automation.
- **CSV** is a flat review table suitable for filtering, assignment, and spreadsheet workflows.
- **Markdown** is a structured human-readable change report suitable for design reviews and source control.

### JSON top-level values

| Value | Meaning |
| --- | --- |
| `comparison_created` | Local timestamp at which the comparison report was assembled. |
| `old_document` | Identity and source information for the earlier input. |
| `new_document` | Identity and source information for the later input. |
| `summary` | Counts of detected changes. Counts are not risk or severity scores. |
| `organized_changes` | The same change records grouped into reviewer-oriented sections and categories. |
| `changes` | Flat list of every detected change record. This is the canonical detailed list. |

### Document identity values

| Value | Meaning |
| --- | --- |
| `path` | Backend-local uploaded JSON path used for this run. |
| `document_name` | Document name supplied by the extractor JSON. |
| `total_pages` | Extracted page count supplied by that document. |

### `summary` values

| Value | Meaning |
| --- | --- |
| `total_changes` | Number of records in `changes`. One engineering edit can produce more than one record when it affects multiple detectable aspects. |
| `by_area` | Counts by content area, such as requirement, section, table, figure, note, page, acronym, or metadata. |
| `by_change_type` | Counts by operation, normally added, removed, modified, or moved. |
| `by_difference_category` | Counts by the comparator's more specific classification, such as numeric or requirement-strength change. |

### Change-record values

Not every change type populates every value. Empty values mean that the field is not applicable or was unavailable; they must not be treated as proof that no source content existed.

| Value | Meaning |
| --- | --- |
| `change_id` | Run-local stable display ID for one reported change. |
| `area` | Kind of document object that changed. |
| `change_type` | High-level operation: added, removed, modified, or moved. |
| `difference_category` | More specific deterministic classification of the difference. |
| `identifier` | Best available source identifier, heading, name, or key for the changed item. |
| `old_value` | Reviewer-facing content from the older document. Empty for additions. |
| `new_value` | Reviewer-facing content from the newer document. Empty for removals. |
| `detail` | Concise explanation of what the comparator detected. |
| `similarity` | Text similarity in the range 0 to 1 when similarity matching was used. It is a matching aid, not a correctness, coverage, risk, or quality score. |
| `old_page` | Earlier page number or page range when known. |
| `new_page` | Later page number or page range when known. |
| `page_shift` | Signed page-number offset inferred for a structural relocation. |
| `display_title` | Human-readable heading used in reports. |
| `report_section` | CSV-only reviewer section derived from the change classification. |
| `report_category` | CSV-only reviewer category derived from the change classification. |

The comparator uses exact keys first, then normalised content and bounded similarity matching. Engineering identifiers and numeric changes should still be reviewed against the original specifications.

## 20. Extraction-quality output

Typical filename: `quality_report_<timestamp>.json`.

### Why this file exists

This report measures how completely and consistently an extractor JSON represents its source material. It evaluates extraction quality, not the technical quality of the specification and not verification coverage.

### Top-level values

| Value | Meaning |
| --- | --- |
| `inputs` | Paths and threshold used to calculate the report. |
| `scores` | The three named quality dimensions, their formulas, status, and component details. |
| `overall_percentage` | Arithmetic mean of completeness, accuracy, and table/figure capture. The three dimensions have equal weight. |
| `overall_status` | `pass` when `overall_percentage` is at least the selected threshold; otherwise `fail`. |

### `inputs` values

| Value | Meaning |
| --- | --- |
| `json` | Extractor JSON being assessed. |
| `pdf` | Source PDF used for fidelity and capture checks, or `null` when unavailable. |
| `gold_json` | Manually checked reference extraction, or `null`. When present, it changes the accuracy components. |
| `threshold` | User-selected pass/fail boundary from 0 to 100. It does not change any percentage calculation. |

### Values present for every named score

| Value | Meaning |
| --- | --- |
| `percentage` | Arithmetic mean of that score's component percentages. |
| `status` | `pass` if `percentage >= threshold`; otherwise `fail`. |
| `formula` | Exact component names included in the mean. |
| `details` | Component name-to-percentage mapping used to reproduce the score. |

### Completeness components

| Value | Meaning |
| --- | --- |
| `required_json_field_score` | Percentage of required top-level extractor fields present. |
| `page_coverage_score` | Extracted page coverage relative to the available source page count. |
| `text_coverage_score` | Extracted page-text character coverage relative to source PDF text, capped at 100%. |
| `semantic_chunk_coverage_score` | Whether expected semantic chunk coverage is present across extracted content. |
| `record_field_completeness_score` | Population rate of required values within extracted records. |
| `cross_reference_recall_score` | Percentage of source section/table references also captured in JSON. |
| `requirement_recall_score` | Percentage of source lines matching normative requirement syntax represented as requirements. |

### Accuracy components without a gold JSON

| Value | Meaning |
| --- | --- |
| `page_text_fidelity_score` | Mean text similarity between each source PDF page and its extracted page text. |
| `requirement_traceability_score` | Percentage of extracted requirements whose text can be found in source PDF text. |
| `category_consistency_score` | Agreement between stored categories and deterministic keyword classification. |
| `page_number_accuracy_score` | Percentage of expected source page numbers present in extracted page records. |
| `json_internal_consistency_score` | Pass rate across internal aggregation, section, reference, figure, and table checks. |
| `category_consistency_priority_score` | Agreement with the scored category classifier and its documented tie-break order. |
| `axi_signal_fidelity_score` | Recall of detected AXI-style signal identifiers. |
| `riscv_csr_fidelity_score` | Recall of detected RISC-V ISA and CSR identifiers. |

### Accuracy components with a gold JSON

| Value | Meaning |
| --- | --- |
| `requirement_f1_score` | F1 measure comparing normalised requirement multiplicities with the gold extraction. |
| `figure_caption_f1_score` | F1 measure for figure captions versus the gold extraction. |
| `table_caption_f1_score` | F1 measure for table captions versus the gold extraction. |
| `page_text_fidelity_score` | Source-PDF page text similarity described above. |
| `json_internal_consistency_score` | Internal consistency pass rate described above. |

### Table and figure capture components

| Value | Meaning |
| --- | --- |
| `table_detection_f1_score` | F1 comparison between source PDF table detections and extracted table records by page. |
| `table_caption_f1_score` | F1 comparison of source and extracted table captions. |
| `table_file_existence_score` | Percentage of table records whose referenced CSV files exist. |
| `figure_caption_f1_score` | F1 comparison of source and extracted figure captions. |
| `image_capture_f1_score` | F1 comparison between PDF images and captured image records by page. |

F1 scores combine precision and recall. An empty expected and empty captured set scores 100%; an empty set on only one side scores 0%. This convention prevents a document with no relevant objects from being penalised, but it can make sparse documents appear stronger.

## 21. Troubleshooting

### Structured-output validation errors

Restart with the current backend and rerun. The schema distinguishes `scenario_type` from `coverage`, retries malformed batches, clears uncovered test content, and rejects incomplete covered/partial rows.

### Coverage will not run

Provide a complete set of requirements, vPlan, edge-case, and weak-language files. Cached backend paths can expire if the backend restarts or output files move.

### Weak-language download fails

Current outputs are stored under `outputs/weak_language`. Ensure the frontend and backend are from the same release.

### PDF extraction finds few or no requirements

Confirm the PDF contains selectable text rather than page images. Review whether its headings and normative language match the configured extraction regular expressions. OCR image-only documents first, then run the quality checker against the source PDF.

### Backend reports `No module named 'fitz'` or `pymupdf`

The active backend environment does not contain PyMuPDF, or an older environment has not been refreshed since extraction was added. Run `python -m pip install -r Backend/requirements.txt` from the repository root. If necessary, install only the missing package with `python -m pip install pymupdf`. The API now loads the PDF parser lazily, so missing PyMuPDF does not prevent unrelated vPlan and coverage routes from starting.

### Mapping is unexpectedly low

Compare `id` in the requirements with `requirement_id` in the vPlan. Check whitespace, changed IDs, duplicates, and files from different runs.

### Mapping is high but weighted coverage is low

This can be correct. Uncovered traceability rows count as mapped but score zero in weighted coverage.

### Frontend score and detail records differ

Clear the browser’s cached workflow state and rerun with a matched file set. The headline testability score uses final deterministic statuses; the separate model-assisted result appears as `model_testability`.

### Large run fails after several batches

The terminal identifies the failing stage and batch. Adjust `REQUIREMENT_CATEGORY_BATCH_SIZE`, `VPLAN_CATEGORY_BATCH_SIZE`, or `COVERAGE_MODEL_BATCH_SIZE` in `.env`, then rerun. The vPlan workflow does not checkpoint completed batches. Coverage reviewer batches continue after exhausted retries and mark missing model assessments `unclear` rather than claiming success.

## 22. Known limitations

- Model outputs are non-deterministic. Schemas, strict prompts, post-processing, and retries reduce error but do not prove technical correctness.
- The tool cannot know design behaviour that is absent from the requirements. Correctly uncovered results may be common for incomplete source material.
- Final coverage is stricter than the vPlan but still evaluates generated artefacts and heuristic ambiguity evidence; it is not simulation, formal, code, assertion, or functional coverage.
- Requirement mapping measures ID linkage only. An uncovered traceability row can produce 100% mapping.
- Weighted coverage gives every requirement equal importance and only weights by final coverage state. It does not model safety impact, verification effort, risk, or project priority.
- The model-assisted granularity assessment can vary between runs.
- A separate model-assisted testability diagnostic exists and may differ from the headline final testability score because they answer related but different questions.
- Weak-language checking is intentionally recall-heavy. It can flag valid optional behaviour, descriptive text, headings, examples, and requirements written without configured normative terms.
- Edge-case extraction only examines requirements selected by the weak-language stage, so it can miss edge cases in strongly worded requirements.
- Edge cases and weak-language flags are linked by exact requirement ID. Missing or duplicate IDs reduce reliability.
- Duplicate requirement IDs are reported but not automatically repaired.
- The whole-spec taxonomy improves consistency but is still model-generated. It can merge unlike concerns or separate related ones and must be reviewed.
- Parent categories are capped at 12, but subcategories add detail. A very broad parent still has to be split at `VPLAN_CATEGORY_BATCH_SIZE`; relationships across those chunks can be missed.
- Requirements assigned to different parent categories are not retrieved into the same vPlan call. `supporting_requirement_ids` exposes used cross-requirement evidence within a batch but does not prove that the relationship is correct.
- If a requirement-assignment batch exhausts its retries, its rows continue as `Uncategorised`; the terminal and categorised-requirements metadata identify failed batches.
- Coverage model batches that exhaust retries produce `unclear` assessments for affected mapped requirements rather than optimistic results.
- Chapter extraction is for testing. Removing other chapters can remove definitions, exceptions, encodings, timing rules, and configuration context.
- Test-name generation depends on `test_description`. Names may be generic when descriptions are generic. Uncovered rows intentionally receive no test name.
- Category/subcategory-based priorities are user-selected workflow ordering, not calculated engineering criticality.
- Token and cost totals depend on callback reporting. Cost uses a hard-coded local price table that can become stale and is not an invoice.
- Runtime outputs and uploads are stored locally without authentication or a retention policy. The application is intended for controlled local/research use, not direct public deployment.
- Browser state uses `localStorage`; uploaded `File` objects do not survive a reload, and cached backend paths are not portable to another server.
- Timestamp-based filenames can collide when concurrent runs write the same output type within one second.
- Download resolution uses basenames across known output directories. Identical filenames in different directories can be ambiguous.
- There is no resume/checkpoint feature for a partially completed vPlan run.
- PDF extraction is rule-based and text-based. Image-only pages, unusual layouts, mathematical notation, multi-column reading order, diagrams, and wording outside the configured regular expressions can be missed or misordered.
- Extracted requirement IDs are stable only for the content and ordering of one run. Editing earlier pages can renumber later requirements, which can affect version comparison and traceability.
- Table CSV files reflect PyMuPDF table detection and can omit merged cells, visual associations, or tables whose layout is not recognised.
- Specification comparison operates on extractor JSON rather than the original PDFs. Extraction changes can therefore appear as specification changes.
- Similarity matching is heuristic and bounded to a candidate set; large reorganisations, repeated boilerplate, and renumbering can create missed or incorrect pairings.
- Quality results without a source PDF or gold JSON rely on fewer independent sources of truth and must be interpreted cautiously.
- Empty expected and captured sets score 100% in F1 calculations. This is mathematically explicit but can inflate results for documents with no tables, figures, or images.
