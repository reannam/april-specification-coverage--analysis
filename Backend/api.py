from pathlib import Path
from urllib.parse import urlparse
import shutil
import uuid
import json

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from Backend.config import UPLOAD_DIR, OUTPUT_DIR
from Backend.pre_processing.agent_scheduler import build_workflow
from Backend.coverage.coverage_workflow import run_coverage_workflow
from Backend.post_processing.prioritise_vplan import (
    prioritise_vplan,
)

app = FastAPI(
    title="Specification Coverage Analysis API",
    description=(
        "Runs vPlan generation, edge-case analysis, and coverage analysis "
        "against an uploaded specification JSON file."
    ),
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


WORKFLOW = build_workflow()


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


def save_and_validate_uploaded_json(uploaded_file: UploadFile) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if not uploaded_file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    if not uploaded_file.filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=400,
            detail="Only .json specification files are supported.",
        )

    upload_id = uuid.uuid4().hex
    safe_filename = Path(uploaded_file.filename).name
    uploaded_file_path = UPLOAD_DIR / f"{upload_id}_{safe_filename}"

    with uploaded_file_path.open("wb") as buffer:
        shutil.copyfileobj(uploaded_file.file, buffer)

    try:
        with uploaded_file_path.open("r", encoding="utf-8") as file:
            json.load(file)
    except json.JSONDecodeError as error:
        uploaded_file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file is not valid JSON: {error}",
        ) from error

    return uploaded_file_path


def normalise_existing_output_path(path_value: str) -> Path:
    cleaned = path_value.strip().replace("\\", "/")
    cleaned = cleaned.removeprefix("./")

    if cleaned.startswith(("http://", "https://")):
        cleaned = urlparse(cleaned).path

    if cleaned.startswith("/api/download/"):
        filename = Path(cleaned).name
        return resolve_downloadable_file(filename)

    if cleaned.startswith("api/download/"):
        filename = Path(cleaned).name
        return resolve_downloadable_file(filename)

    if cleaned.startswith("/outputs/"):
        return OUTPUT_DIR.parent / cleaned.removeprefix("/")

    if cleaned.startswith("outputs/"):
        return OUTPUT_DIR.parent / cleaned

    if cleaned.startswith("/backend/outputs/"):
        return OUTPUT_DIR.parent / cleaned.removeprefix("/backend/")

    if cleaned.startswith("backend/outputs/"):
        return OUTPUT_DIR.parent / cleaned.removeprefix("backend/")

    path = Path(cleaned)

    if path.is_absolute():
        return path

    return OUTPUT_DIR.parent / path


def resolve_downloadable_file(filename: str) -> Path:
    safe_filename = Path(filename).name

    possible_paths = [
        OUTPUT_DIR / safe_filename,
        OUTPUT_DIR / "edge_cases" / safe_filename,
        OUTPUT_DIR / "langsmith_logs" / safe_filename,
        OUTPUT_DIR / "traceability" / safe_filename,
        OUTPUT_DIR / "requirement_test_links" / safe_filename,
        OUTPUT_DIR / "blocked_tests" / safe_filename,
        OUTPUT_DIR / "coverage_status" / safe_filename,
        OUTPUT_DIR / "final_coverage_report" / safe_filename,
        OUTPUT_DIR / "coverage_summary" / safe_filename,
        OUTPUT_DIR / "usage_charts" / safe_filename,
        OUTPUT_DIR / "weak_words" / safe_filename,
        OUTPUT_DIR / "vplans" / safe_filename,
        OUTPUT_DIR / "coverage_upload_cache" / safe_filename,
        OUTPUT_DIR / "prioritised_vplans" / safe_filename,
    ]

    file_path = next((path for path in possible_paths if path.exists()), None)

    if file_path is None:
        raise HTTPException(status_code=404, detail=f"File not found: {safe_filename}")

    return file_path


async def resolve_coverage_input(
    *,
    label: str,
    existing_path: str | None,
    uploaded_file: UploadFile | None,
) -> Path:
    if uploaded_file and uploaded_file.filename:
        return save_and_validate_uploaded_json(uploaded_file)

    if existing_path:
        resolved_path = normalise_existing_output_path(existing_path)

        if not resolved_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"{label} path does not exist: {resolved_path}",
            )

        return resolved_path

    raise HTTPException(
        status_code=400,
        detail=f"Missing {label}. Provide either a cached path or upload a JSON file.",
    )


def make_download_url(file_path: str | Path | None) -> str | None:
    if not file_path:
        return None

    return f"/api/download/{Path(file_path).name}"


def make_filename(file_path: str | Path | None) -> str | None:
    if not file_path:
        return None

    return Path(file_path).name


@app.post("/api/run-agents")
async def run_agents(requirements_file: UploadFile = File(...)):
    try:
        uploaded_file_path = save_and_validate_uploaded_json(requirements_file)

        result = WORKFLOW.invoke({"requirements_file": str(uploaded_file_path)})

        vplan_output_file = result.get("vplan_output_file")
        edge_case_output_file = result.get("edge_case_output_file")
        langsmith_log_file = result.get("langsmith_log_file")
        requirement_test_links_file = result.get("requirement_test_links_file")
        preprocessed_requirements_file = result.get("preprocessed_requirements_file")
        blocked_test_report_file = result.get("blocked_test_report_file")
        weak_words_file = result.get("weak_words_file") or result.get(
            "weak_words_output_file"
        )

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

        if not weak_words_file:
            raise HTTPException(
                status_code=500,
                detail=(
                    "The workflow completed but did not return a "
                    "weak-language output file."
                ),
            )

        vplan_path = Path(vplan_output_file).resolve()
        edge_case_path = Path(edge_case_output_file).resolve()
        weak_words_path = Path(weak_words_file).resolve()

        if not vplan_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Generated vPlan file was not found.",
            )

        if not edge_case_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Generated edge-case file was not found.",
            )

        if not weak_words_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Generated weak-language file was not found.",
            )

        with vplan_path.open("r", encoding="utf-8") as file:
            vplan_data = json.load(file)

        with weak_words_path.open("r", encoding="utf-8") as file:
            weak_language_data = json.load(file)

        if not isinstance(vplan_data, dict):
            raise HTTPException(
                status_code=500,
                detail="Generated vPlan is not a JSON object.",
            )

        if not isinstance(vplan_data.get("feature_list"), list):
            raise HTTPException(
                status_code=500,
                detail=("Generated vPlan does not contain a " "'feature_list' array."),
            )

        return {
            "message": "Agent workflow completed successfully.",
            "vplan": vplan_data,
            "weak_language": weak_language_data,
            "vplan_download_url": make_download_url(vplan_path),
            "edge_cases_download_url": make_download_url(edge_case_path),
            "weak_words_download_url": make_download_url(weak_words_path),
            "vplan_filename": vplan_path.name,
            "edge_cases_filename": edge_case_path.name,
            "weak_words_filename": weak_words_path.name,
            "vplan_file": str(vplan_path),
            "edge_case_file": str(edge_case_path),
            "weak_words_file": str(weak_words_path),
            "langsmith_log_download_url": make_download_url(langsmith_log_file),
            "langsmith_log_filename": make_filename(langsmith_log_file),
            "input_tokens": token_summary.get(
                "input_tokens",
                token_summary.get("prompt_tokens"),
            ),
            "output_tokens": token_summary.get(
                "output_tokens",
                token_summary.get("completion_tokens"),
            ),
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
            "requirement_test_links_download_url": make_download_url(
                requirement_test_links_file
            ),
            "requirement_test_links_filename": make_filename(
                requirement_test_links_file
            ),
            "preprocessed_requirements_filename": make_filename(
                preprocessed_requirements_file
            ),
            "blocked_test_report_download_url": make_download_url(
                blocked_test_report_file
            ),
            "blocked_test_report_filename": make_filename(blocked_test_report_file),
            "requirements_file": str(uploaded_file_path),
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


@app.post("/api/run-coverage")
async def run_coverage(
    requirements_file: UploadFile | None = File(None),
    requirements_path: str | None = Form(None),
    vplan_file: str | None = Form(None),
    edge_case_file: str | None = Form(None),
    weak_words_file: str | None = Form(None),
    vplan_upload: UploadFile | None = File(None),
    edge_case_upload: UploadFile | None = File(None),
    weak_words_upload: UploadFile | None = File(None),
):
    """
    Runs the coverage workflow using existing files.

    Inputs can come from either:
    - cached paths from a previous vPlan generation run
    - manually uploaded JSON files
    """

    try:
        requirements_input_path = await resolve_coverage_input(
            label="requirements file",
            existing_path=requirements_path,
            uploaded_file=requirements_file,
        )

        vplan_path = await resolve_coverage_input(
            label="vPlan file",
            existing_path=vplan_file,
            uploaded_file=vplan_upload,
        )

        edge_case_path = await resolve_coverage_input(
            label="edge-case file",
            existing_path=edge_case_file,
            uploaded_file=edge_case_upload,
        )

        weak_words_path = await resolve_coverage_input(
            label="weak-words file",
            existing_path=weak_words_file,
            uploaded_file=weak_words_upload,
        )

        result = run_coverage_workflow(
            requirements_file=str(requirements_input_path),
            vplan_file=str(vplan_path),
            edge_case_file=str(edge_case_path),
            weak_words_file=str(weak_words_path),
        )

        vplan_file_result = result.get("vplan_file")
        edge_case_file_result = result.get("edge_case_file")
        weak_words_file_result = result.get("weak_words_file")
        coverage_status_file = result.get("coverage_status_file")

        final_output_files = result.get("final_coverage_output_files", {})
        final_report = result.get("final_coverage_report", {})

        total_usage = result.get("total_usage", {})
        usage_report_files = result.get("usage_report_files", {})

        if not coverage_status_file:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Coverage workflow completed but did not return a coverage "
                    "status file."
                ),
            )

        coverage_summary = dict(final_report.get("coverage_summary", {}))
        coverage_percentages = dict(final_report.get("coverage_percentages", {}))

        granularity_result = result.get(
            "granularity_result",
            {},
        )

        if granularity_result:
            coverage_percentages.setdefault(
                "granularity_adequacy",
                granularity_result.get(
                    "granularity_adequacy",
                    0,
                ),
            )

            coverage_summary.setdefault(
                "granularity_mapped_requirements",
                granularity_result.get(
                    "mapped_requirements",
                    0,
                ),
            )

            coverage_summary.setdefault(
                "granularity_suitable_detail",
                granularity_result.get(
                    "requirements_covered_at_suitable_detail",
                    0,
                ),
            )

            coverage_summary.setdefault(
                "granularity_not_mapped",
                granularity_result.get(
                    "requirements_not_mapped",
                    0,
                ),
            )

        return {
            "message": "Coverage workflow completed successfully.",
            "vplan_download_url": make_download_url(vplan_file_result),
            "vplan_filename": make_filename(vplan_file_result),
            "edge_cases_download_url": make_download_url(edge_case_file_result),
            "edge_cases_filename": make_filename(edge_case_file_result),
            "weak_words_download_url": make_download_url(weak_words_file_result),
            "weak_words_filename": make_filename(weak_words_file_result),
            "coverage_status_download_url": make_download_url(coverage_status_file),
            "coverage_status_filename": make_filename(coverage_status_file),
            "coverage_summary": coverage_summary,
            "coverage_percentages": coverage_percentages,
            "granularity_result": granularity_result,
            "coverage_output_files": {
                key: {
                    "filename": make_filename(path),
                    "download_url": make_download_url(path),
                }
                for key, path in final_output_files.items()
            },
            "input_tokens": total_usage.get(
                "input_tokens",
                total_usage.get("prompt_tokens"),
            ),
            "output_tokens": total_usage.get(
                "output_tokens",
                total_usage.get("completion_tokens"),
            ),
            "total_tokens": total_usage.get("total_tokens"),
            "estimated_cost_usd": total_usage.get("total_cost"),
            "coverage_usage": total_usage,
            "usage_report_files": {
                key: {
                    "filename": filename,
                    "download_url": f"/api/usage-chart/{filename}",
                }
                for key, filename in usage_report_files.items()
            },
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Coverage workflow failed: {error}",
        ) from error

    finally:
        if requirements_file:
            requirements_file.file.close()

        for uploaded_file in (
            vplan_upload,
            edge_case_upload,
            weak_words_upload,
        ):
            if uploaded_file:
                uploaded_file.file.close()


@app.post("/api/prioritise-vplan")
async def prioritise_vplan_endpoint(
    vplan_file: str | None = Form(None),
    vplan_upload: UploadFile | None = File(None),
    priority_1_categories: str = Form(...),
    priority_2_categories: str = Form(...),
):
    """
    Applies deterministic priorities to an existing categorised vPlan.

    The category selections are supplied as JSON arrays:
    - priority_1_categories: highest-priority categories
    - priority_2_categories: medium-priority categories

    All remaining categories receive Priority 3.
    """

    try:
        vplan_path = await resolve_coverage_input(
            label="vPlan file",
            existing_path=vplan_file,
            uploaded_file=vplan_upload,
        )

        try:
            priority_one = json.loads(priority_1_categories)
            priority_two = json.loads(priority_2_categories)
        except json.JSONDecodeError as error:
            raise HTTPException(
                status_code=400,
                detail="Priority categories must be valid JSON arrays.",
            ) from error

        if not isinstance(priority_one, list):
            raise HTTPException(
                status_code=400,
                detail="priority_1_categories must be a JSON array.",
            )

        if not isinstance(priority_two, list):
            raise HTTPException(
                status_code=400,
                detail="priority_2_categories must be a JSON array.",
            )

        priority_one = [str(category) for category in priority_one]
        priority_two = [str(category) for category in priority_two]

        prioritised_output_dir = OUTPUT_DIR / "prioritised_vplans"
        prioritised_output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path = prioritise_vplan(
            vplan_file=vplan_path,
            priority_1_categories=priority_one,
            priority_2_categories=priority_two,
            output_dir=prioritised_output_dir,
        )

        with output_path.open("r", encoding="utf-8") as file:
            updated_vplan = json.load(file)

        return {
            "message": "vPlan priorities updated successfully.",
            "vplan": updated_vplan,
            "vplan_file": str(output_path.resolve()),
            "vplan_filename": output_path.name,
            "vplan_download_url": make_download_url(output_path),
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"vPlan prioritisation failed: {error}",
        ) from error

    finally:
        if vplan_upload:
            vplan_upload.file.close()


@app.get("/api/download/{filename}")
def download_file(filename: str):
    file_path = resolve_downloadable_file(filename)

    if file_path.suffix == ".csv":
        media_type = "text/csv"
    elif file_path.suffix == ".png":
        media_type = "image/png"
    else:
        media_type = "application/json"

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
