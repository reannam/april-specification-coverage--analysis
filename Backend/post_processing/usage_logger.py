import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


# Fill these in with the prices you want to use.
# These are USD per 1 million tokens.
MODEL_PRICES_PER_1M = {
    "gpt-5.5": {
        "input": Decimal("5.00"),
        "output": Decimal("30.00"),
    },
    "gpt-5.4": {
        "input": Decimal("2.50"),
        "output": Decimal("15.00"),
    },
    "gpt-5.4-mini": {
        "input": Decimal("0.75"),
        "output": Decimal("4.50"),
    },
}


def calculate_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    prices = MODEL_PRICES_PER_1M.get(model_name)

    if not prices:
        return Decimal("0")

    input_cost = (Decimal(input_tokens) / Decimal("1000000")) * prices["input"]
    output_cost = (Decimal(output_tokens) / Decimal("1000000")) * prices["output"]

    return input_cost + output_cost


def normalise_usage(
    agent_name: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    total_cost: float | str,
    model_name: str,
) -> dict[str, Any]:
    callback_cost = Decimal(str(total_cost or 0))

    calculated_cost = calculate_cost(
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    final_cost = calculated_cost if calculated_cost > 0 else callback_cost

    return {
        "agent_name": agent_name,
        "model_name": model_name,
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": total_tokens,
        "total_cost": str(final_cost),
    }


def aggregate_usage(*usage_items: dict[str, Any]) -> dict[str, Any]:
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    total_cost = Decimal("0")

    agents = []

    for usage in usage_items:
        if not usage:
            continue

        total_prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        total_completion_tokens += int(usage.get("completion_tokens", 0) or 0)
        total_tokens += int(usage.get("total_tokens", 0) or 0)
        total_cost += Decimal(str(usage.get("total_cost", 0) or 0))

        agents.append(usage)

    return {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "total_cost": str(total_cost),
        "agents": agents,
    }


def append_to_master_usage_file(
    logs_dir: Path,
    run_record: dict[str, Any],
) -> Path:
    master_file = logs_dir / "all_usage_runs.json"

    if master_file.exists():
        with master_file.open("r", encoding="utf-8") as file:
            existing_runs = json.load(file)
    else:
        existing_runs = []

    existing_runs.append(run_record)

    with master_file.open("w", encoding="utf-8") as file:
        json.dump(existing_runs, file, indent=2)

    return master_file


def save_usage_log(
    output_file: Path,
    logs_dir: Path,
    trace_ids: dict[str, str | None],
    usage_summary: dict[str, Any],
) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().isoformat(timespec="seconds")

    log_file = logs_dir / f"{output_file.stem}_usage_log.json"

    log_data = {
        "timestamp": timestamp,
        "output_file": output_file.name,
        "trace_ids": trace_ids,
        "summary": usage_summary,
    }

    with log_file.open("w", encoding="utf-8") as file:
        json.dump(log_data, file, indent=2)

    append_to_master_usage_file(
        logs_dir=logs_dir,
        run_record=log_data,
    )

    return log_file