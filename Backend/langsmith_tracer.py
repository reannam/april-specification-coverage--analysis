import json
import os
import uuid
from pathlib import Path
from typing import Any

from langsmith import Client
from langchain_core.tracers.langchain import wait_for_all_tracers


def is_langsmith_configured() -> bool:
    """Return True if LangSmith is configured enough to export traces."""

    return bool(os.getenv("LANGSMITH_API_KEY"))


def extract_run_value(run: Any, field_name: str) -> Any:
    """
    Safely extract a field from a LangSmith run.

    LangSmith run objects can vary slightly depending on SDK/version,
    so this avoids hard failures when a field is missing.
    """

    return getattr(run, field_name, None)


def serialise_run(run: Any) -> dict:
    """Convert a LangSmith run object into JSON-safe trace data."""

    return {
        "id": str(extract_run_value(run, "id")),
        "trace_id": str(extract_run_value(run, "trace_id")),
        "parent_run_id": (
            str(extract_run_value(run, "parent_run_id"))
            if extract_run_value(run, "parent_run_id")
            else None
        ),
        "name": extract_run_value(run, "name"),
        "run_type": extract_run_value(run, "run_type"),
        "start_time": (
            extract_run_value(run, "start_time").isoformat()
            if extract_run_value(run, "start_time")
            else None
        ),
        "end_time": (
            extract_run_value(run, "end_time").isoformat()
            if extract_run_value(run, "end_time")
            else None
        ),
        "status": extract_run_value(run, "status"),
        "error": extract_run_value(run, "error"),

        # Token usage
        "total_tokens": extract_run_value(run, "total_tokens"),
        "prompt_tokens": extract_run_value(run, "prompt_tokens"),
        "completion_tokens": extract_run_value(run, "completion_tokens"),

        # Cost usage
        "total_cost": extract_run_value(run, "total_cost"),
        "prompt_cost": extract_run_value(run, "prompt_cost"),
        "completion_cost": extract_run_value(run, "completion_cost"),

        # Useful debugging fields
        "inputs": extract_run_value(run, "inputs"),
        "outputs": extract_run_value(run, "outputs"),
        "extra": extract_run_value(run, "extra"),
        "tags": extract_run_value(run, "tags"),
        "metadata": extract_run_value(run, "metadata"),
    }


def save_langsmith_trace_log(
    run_id: uuid.UUID,
    output_file: Path,
    logs_dir: Path,
) -> Path | None:
    """
    Download the LangSmith trace for a run and save it to a matching JSON file.

    Example:
    output_file:
        ../outputs/generated_vplan_2026-06-23_14-12-03.json

    saved log:
        ../outputs/langsmith_logs/generated_vplan_2026-06-23_14-12-03.langsmith.json
    """

    if not is_langsmith_configured():
        print("Skipping LangSmith trace export because LANGSMITH_API_KEY is not set.")
        return None

    wait_for_all_tracers()

    logs_dir.mkdir(parents=True, exist_ok=True)

    client = Client()

    trace_runs = list(client.list_runs(trace_id=run_id))

    log_file = logs_dir / f"{output_file.stem}.langsmith.json"

    trace_log = {
        "vplan_file": output_file.name,
        "trace_id": str(run_id),
        "number_of_runs": len(trace_runs),
        "runs": [serialise_run(run) for run in trace_runs],
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(trace_log, f, indent=2, default=str)

    print(f"LangSmith trace log saved to {log_file}")

    return log_file