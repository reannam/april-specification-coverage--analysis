from typing import Any

from Backend.vPlan.post_processing.usage_logger import normalise_usage


def normalise_requirement_category(value: Any) -> str:
    """Return a stable, bounded category label suitable for grouping."""

    if isinstance(value, list):
        value = next((item for item in value if str(item).strip()), "")

    category = " ".join(str(value or "").split()).strip()
    return category[:80] or "Uncategorised"


def requirement_category(requirement: dict) -> str:
    """Prefer an extracted category, then the requirement type, without guessing."""

    return normalise_requirement_category(
        requirement.get("requirement_category")
        or requirement.get("category")
        or requirement.get("type")
    )


def requirement_subcategory(requirement: dict) -> str:
    """Return the pre-assigned subcategory without deriving new semantics."""

    return normalise_requirement_category(
        requirement.get("requirement_subcategory") or "Uncategorised"
    )


def build_category_batches(
    requirements: list[dict],
    max_batch_size: int,
) -> list[dict[str, Any]]:
    """Group the whole specification by category, then cap oversized groups.

    Category grouping brings related requirements from different chapters together.
    The size cap remains essential because broad categories can contain hundreds of
    requirements and exceed structured-output limits.
    """

    grouped: dict[str, list[dict]] = {}
    for requirement in requirements:
        category = requirement_category(requirement)
        enriched = dict(requirement)
        enriched["planning_category"] = category
        enriched["planning_subcategory"] = requirement_subcategory(requirement)
        grouped.setdefault(category, []).append(enriched)

    batches: list[dict[str, Any]] = []
    for category, category_requirements in grouped.items():
        # Keeping each subcategory contiguous reduces the chance that an oversized
        # parent category separates closely related requirements across chunks.
        category_requirements.sort(
            key=lambda item: (str(item["planning_subcategory"]).casefold(),)
        )
        chunks = chunk_requirements(category_requirements, max_batch_size)
        for category_part, chunk in enumerate(chunks, start=1):
            batches.append(
                {
                    "category": category,
                    "category_part": category_part,
                    "category_parts": len(chunks),
                    "requirements": chunk,
                }
            )

    return batches


def chunk_requirements(
    requirements: list[dict],
    batch_size: int = 30,
) -> list[list[dict]]:
    """Bound structured-output size so large specifications remain recoverable."""

    return [
        requirements[index : index + batch_size]
        for index in range(0, len(requirements), batch_size)
    ]


def filter_edge_cases_for_batch(
    edge_cases: dict | None,
    requirements_batch: list[dict],
) -> dict:
    """Send each generation batch only edge cases linked to its requirements."""

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
    """Preserve the model ID and add a visible suffix when batches collide."""

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
    """Aggregate batch telemetry without losing the per-batch audit records."""

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
