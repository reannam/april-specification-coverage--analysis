from pathlib import Path
import shutil
import uuid
import json

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from Backend.config import UPLOAD_DIR, OUTPUT_DIR
from Backend.pre_processing.agent_scheduler import build_workflow


app = FastAPI(
    title="Specification Coverage Analysis API",
    description="Runs the vPlan and edge-case agents against an uploaded specification JSON file.",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/run-agents")
async def run_agents(requirements_file: UploadFile = File(...)):
    if not requirements_file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    if not requirements_file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json specification files are supported.")

    upload_id = uuid.uuid4().hex
    safe_filename = Path(requirements_file.filename).name
    uploaded_file_path = UPLOAD_DIR / f"{upload_id}_{safe_filename}"

    try:
        with uploaded_file_path.open("wb") as buffer:
            shutil.copyfileobj(requirements_file.file, buffer)

        try:
            with uploaded_file_path.open("r", encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as error:
            uploaded_file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail=f"Uploaded file is not valid JSON: {error}",
            ) from error

        workflow = build_workflow()

        result = workflow.invoke({
            "requirements_file": str(uploaded_file_path)
        })

        vplan_output_file = result.get("vplan_output_file")
        edge_case_output_file = result.get("edge_case_output_file")
        langsmith_log_file = result.get("langsmith_log_file")
        requirement_test_links_file = result.get("requirement_test_links_file")
        preprocessed_requirements_file = result.get("preprocessed_requirements_file")
        blocked_test_report_file = result.get("blocked_test_report_file")

        token_summary = result.get("langsmith_summary", {})
        usage_reports = result.get("usage_reports", {})

        if not vplan_output_file:
            raise HTTPException(
                status_code=500,
                detail="The workflow completed but did not return a vPlan output file.",
            )

        if not edge_case_output_file:
            raise HTTPException(
                status_code=500,
                detail="The workflow completed but did not return an edge-case output file.",
            )

        vplan_path = Path(vplan_output_file).resolve()
        edge_case_path = Path(edge_case_output_file).resolve()

        if not vplan_path.exists():
            raise HTTPException(status_code=500, detail="Generated vPlan file was not found.")

        if not edge_case_path.exists():
            raise HTTPException(status_code=500, detail="Generated edge-case file was not found.")

        return {
            "message": "Workflow completed successfully.",

            "vplan_download_url": f"/api/download/{vplan_path.name}",
            "edge_cases_download_url": f"/api/download/{edge_case_path.name}",

            "vplan_filename": vplan_path.name,
            "edge_cases_filename": edge_case_path.name,

            "langsmith_log_download_url": (
                f"/api/download/{Path(langsmith_log_file).name}" if langsmith_log_file else None
            ),
            "langsmith_log_filename": (
                Path(langsmith_log_file).name if langsmith_log_file else None
            ),

            "input_tokens": token_summary.get("prompt_tokens"),
            "output_tokens": token_summary.get("completion_tokens"),
            "total_tokens": token_summary.get("total_tokens"),
            "estimated_cost_usd": token_summary.get("total_cost"),

            "agent_usage": token_summary.get("agents", []),

            "usage_chart_urls": {
                key: f"/api/usage-chart/{filename}"
                for key, filename in usage_reports.items()
                if filename.endswith(".png")
            },
            "usage_csv_urls": {
                key: f"/api/usage-chart/{filename}"
                for key, filename in usage_reports.items()
                if filename.endswith(".csv")
            },

            "requirement_test_links_download_url": (
                f"/api/download/{Path(requirement_test_links_file).name}"
                if requirement_test_links_file else None
            ),
            "requirement_test_links_filename": (
                Path(requirement_test_links_file).name
                if requirement_test_links_file else None
            ),
            "preprocessed_requirements_filename": (
                Path(preprocessed_requirements_file).name
                if preprocessed_requirements_file else None
            ),
            "blocked_test_report_download_url": (
                f"/api/download/{Path(blocked_test_report_file).name}"
                if blocked_test_report_file else None
            ),
            "blocked_test_report_filename": (
                Path(blocked_test_report_file).name
                if blocked_test_report_file else None
            ),
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Agent workflow failed: {error}",
        ) from error

    finally:
        requirements_file.file.close()


@app.get("/api/download/{filename}")
def download_file(filename: str):
    safe_filename = Path(filename).name

    possible_paths = [
        OUTPUT_DIR / safe_filename,
        OUTPUT_DIR / "edge_cases" / safe_filename,
        OUTPUT_DIR / "langsmith_logs" / safe_filename,
        OUTPUT_DIR / "traceability" / safe_filename,
        OUTPUT_DIR / "requirement_test_links" / safe_filename,
        OUTPUT_DIR / "blocked_tests" / safe_filename,
    ]

    file_path = next((path for path in possible_paths if path.exists()), None)

    if file_path is None:
        raise HTTPException(status_code=404, detail="File not found.")

    media_type = "text/csv" if file_path.suffix == ".csv" else "application/json"

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=media_type,
    )

@app.get("/api/usage-chart/{filename}")
def get_usage_chart(filename: str):
    safe_filename = Path(filename).name
    file_path = OUTPUT_DIR / "usage_charts" / safe_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Usage chart not found.")

    media_type = "image/png" if file_path.suffix == ".png" else "text/csv"

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type=media_type,
    )