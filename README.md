# Specification Coverage Analysis

This repository contains an AI-assisted workflow for analysing structured requirements, generating a verification plan (vPlan), and producing edge-case analysis output. The project currently combines a FastAPI backend with a Vite frontend so the workflow can be run from a browser.

It takes a JSON requirements file as input and produces:

- A verification plan containing tests mapped to requirements
- Edge-case analysis based on weak, ambiguous, optional, or conditional wording
- Traceability information linking generated tests back to requirements
- Usage and tracing metadata for LangSmith-style analysis

---

## Project Structure

```text
.
├── .gitignore
├── Backend/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── coverage_analysis_agent.py
│   │   ├── edge_case_agent.py
│   │   └── vplan_generator_agent.py
│   ├── api.py
│   ├── coverage/
│   │   ├── __init__.py
│   │   ├── coverage_workflow.py
│   │   └── run_coverage_analysis.py
│   ├── main.py
│   ├── post_processing/
│   │   ├── __init__.py
│   │   ├── analyse_usage_logs.py
│   │   └── usage_logger.py
│   ├── pre_processing/
│   │   ├── __init__.py
│   │   ├── agent_scheduler.py
│   │   ├── data_class.py
│   │   └── preprocess_requirements.py
│   ├── report_generation/
│   │   ├── blocked_test_report_generator.py
│   │   ├── traceability_record_generator.py
│   │   ├── vplan_traceability_check.py
│   │   └── weak_language_check.py
│   └── requirements.txt
├── Frontend/
│   ├── .gitignore
│   ├── index.html
│   ├── public/
│   ├── src/
│   │   ├── App.css
│   │   ├── App.tsx
│   │   ├── assets/
│   │   ├── index.css
│   │   └── main.tsx
├── ambiguous-requirements.json
├── document_tiny_subset.json
├── example-requirements.json
├── example-vplan.json
├── outputs/
├── uploads/
└── README.md
```

The current backend entry points are Backend/api.py (FastAPI service) and Backend/main.py (workflow runner using example-requirements.json).

---

## Features

### vPlan Generation

The vPlan generator reads a JSON requirements file and creates a structured verification plan. Each generated test typically includes a test ID, requirement ID, requirement text, test description, constraints, steps, expected results, priority, and coverage information.

### Edge-Case Analysis

The edge-case agent identifies cases implied by weak or ambiguous requirement wording such as may, should, where applicable, normally, could, if supported, and as appropriate.

### Traceability and Usage Logging

Generated tests are checked for traceability. The workflow also produces requirement-test link exports, blocked test reports, usage summaries, token counts, and output plots.

---

## Prerequisites

You will need:

- Python 3.11 or later
- Node.js 18 or later
- npm
- An OpenAI API key
- Optional LangSmith/LangChain environment variables if you want tracing

---

## Backend Setup

From the project root, create and activate a virtual environment:

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install the backend dependencies from the repository root:

```bash
python -m pip install -r Backend/requirements.txt
```

Create or edit the project-root .env file and add your credentials:

```env
OPENAI_API_KEY=your_openai_api_key_here

# Optional, but recommended if you want LangSmith tracing
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=specification-analysis
```

If your LangChain/LangSmith version expects the older variable names, you can also add:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=specification-analysis
```

---

## Running the Backend

### Option 1: Run the workflow directly

This runs the workflow with the repository's example requirements file:

```bash
python3 Backend/main.py
```

### Option 2: Run the FastAPI service

This starts the API used by the frontend:

```bash
uvicorn Backend.api:app --reload --host 127.0.0.1 --port 8000
```

The API exposes health and upload endpoints at /api/health and /api/run-agents.

---

## Frontend Setup

Navigate to the frontend directory:

```bash
cd Frontend
```

Install dependencies:

```bash
npm install
```

Run the frontend:

```bash
npm run dev
```

The frontend is served at http://localhost:5173 by default. The current frontend code calls the backend at http://localhost:8000, so both services should be running on those ports for local use.

---

## Expected Output

Generated files are written under the repository's outputs directory. Typical output locations include:

```text
outputs/
outputs/blocked_tests/
outputs/coverage_reports/
outputs/edge_cases/
outputs/langsmith_logs/
outputs/node_architecture_graph/
outputs/traceability/
outputs/usage_charts/
outputs/weak_language/
```

---

## Input Requirements Format

The backend expects a JSON array of requirements. The repository includes example files at example-requirements.json and ambiguous-requirements.json. The workflow preprocesses the uploaded JSON before analysis.

Example structure:

```json
[
  {
    "id": "REQ_I2C_001",
    "description": "The controller must support normal-mode I2C operation.",
    "text": "The I2C controller shall support 100 Kbps normal-mode operation.",
    "source_section": "1.1 I2C Features",
    "signals": ["scl", "sda"],
    "type": "functional_requirement"
  }
]
```

Each requirement should include at least an id, description, text, source_section, signals, and type.

---

## Example Workflow

1. Prepare or select a requirements JSON file.
2. Start the backend API.
3. Start the frontend.
4. Upload the JSON file through the frontend.
5. Review the generated vPlan, edge-case analysis, and usage metrics.
6. Download the generated files from the API responses.

---

## Troubleshooting

### OPENAI_API_KEY not found

Ensure the repository-root .env file exists and contains your OpenAI key.

### Frontend cannot connect to the backend

Check that:

- The backend is running on http://localhost:8000
- The frontend is still pointing to that URL in Frontend/src/App.tsx
- CORS is enabled for localhost:5173 in Backend/api.py

### Import errors from backend modules

Run commands from the project root, not from inside Backend. If needed, set:

```bash
export PYTHONPATH=.
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH="."
```

---

## Disclaimer

This tool is intended to support verification planning and specification analysis. Generated vPlans should be reviewed by a human verification engineer before being used as final verification artefacts.