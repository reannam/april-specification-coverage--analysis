from typing import Any

from Backend.post_processing.usage_logger import normalise_usage


def chunk_requirements(
    requirements: list[dict],
    batch_size: int = 30,
) -> list[list[dict]]:
    return [
        requirements[index : index + batch_size]
        for index in range(0, len(requirements), batch_size)
    ]


def filter_edge_cases_for_batch(
    edge_cases: dict | None,
    requirements_batch: list[dict],
) -> dict:
    if not edge_cases:
        return {"edge_cases": []}

    batch_requirement_ids = {
        requirement.get("id")
        for requirement in requirements_batch
        if isinstance(requirement, dict) and requirement.get("id")
    }

    return {
        "edge_cases": [
            edge_case
            for edge_case in edge_cases.get("edge_cases", [])
            if edge_case.get("requirement_id") in batch_requirement_ids
        ]
    }


def ensure_unique_test_ids(rows: list[dict]) -> list[dict]:
    seen: dict[str, int] = {}

    for row in rows:
        test_id = row.get("test_id") or "TEST_UNKNOWN"

        if test_id not in seen:
            seen[test_id] = 1
            row["test_id"] = test_id
            continue

        seen[test_id] += 1
        row["test_id"] = f"{test_id}_DUP{seen[test_id]}"

    return rows


def to_int(value: Any) -> int:
    if value is None:
        return 0

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def to_float(value: Any) -> float:
    if value is None:
        return 0.0

    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "").strip()

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def combine_usage(batch_usages: list[dict]) -> dict:
    prompt_tokens = sum(to_int(usage.get("prompt_tokens")) for usage in batch_usages)

    completion_tokens = sum(
        to_int(usage.get("completion_tokens")) for usage in batch_usages
    )

    total_tokens = sum(to_int(usage.get("total_tokens")) for usage in batch_usages)

    total_cost = sum(to_float(usage.get("total_cost")) for usage in batch_usages)

    combined = normalise_usage(
        agent_name="vplan_generator",
        input_tokens=prompt_tokens,
        output_tokens=completion_tokens,
        total_tokens=total_tokens,
        total_cost=total_cost,
        model_name="gpt-5.4",
    )

    combined["number_of_batches"] = len(batch_usages)
    combined["batches"] = batch_usages

    return combined
