"""Shared bounded execution for model-assisted coverage reviewers."""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_community.callbacks.manager import get_openai_callback

from Backend.config import COVERAGE_MODEL_BATCH_RETRIES, COVERAGE_MODEL_BATCH_SIZE
from Backend.vPlan.post_processing.usage_logger import aggregate_usage, normalise_usage


def chunk_items(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    return [
        items[index : index + COVERAGE_MODEL_BATCH_SIZE]
        for index in range(0, len(items), COVERAGE_MODEL_BATCH_SIZE)
    ]


def is_quota_exhausted(error: Exception) -> bool:
    """Distinguish exhausted account quota from a transient rate limit."""

    message = str(error).casefold()
    return "insufficient_quota" in message or "quota has been exceeded" in message


def run_review_batches(
    *,
    review_name: str,
    model_name: str,
    payloads: list[dict[str, Any]],
    get_agent: Callable[[], Any],
) -> tuple[list[Any], dict[str, Any]]:
    """Run structured reviews in batches and continue conservatively on failure.

    Missing assessments are handled by each caller as ``unclear``. This ensures a
    transient malformed batch cannot discard deterministic coverage results.
    """

    batches = chunk_items(payloads)
    assessments: list[Any] = []
    usage_records: list[dict[str, Any]] = []
    failed_batches: list[int] = []
    failed_requirement_ids: list[str] = []
    quota_exhausted = False

    submitted_test_ids = [
        str(test.get("test_id"))
        for payload in payloads
        for test in payload.get("linked_vplan_items", [])
        if test.get("test_id") is not None
    ]

    if not batches:
        usage = aggregate_usage()
        usage.update(
            {
                "number_of_batches": 0,
                "batch_size": COVERAGE_MODEL_BATCH_SIZE,
                "failed_batches": [],
                "failed_requirement_ids": [],
                "quota_exhausted": False,
                "assessment_items_submitted": 0,
                "vplan_items_submitted": 0,
                "test_ids_submitted": [],
            }
        )
        return assessments, usage

    print(
        f"[Coverage: {review_name}] {len(payloads)} mapped requirements across "
        f"{len(batches)} batches (maximum {COVERAGE_MODEL_BATCH_SIZE} per batch)."
    )

    for batch_number, batch in enumerate(batches, start=1):
        completed = False
        for attempt_number in range(1, COVERAGE_MODEL_BATCH_RETRIES + 2):
            print(
                f"[Coverage: {review_name}] Starting batch "
                f"{batch_number}/{len(batches)}, attempt {attempt_number}."
            )
            try:
                with get_openai_callback() as callback:
                    response = get_agent().invoke(
                        {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": json.dumps(
                                        {"assessment_items": batch},
                                        separators=(",", ":"),
                                        ensure_ascii=False,
                                    ),
                                }
                            ]
                        }
                    )

                structured = response.get("structured_response")
                if structured is None:
                    raise ValueError("Agent returned no structured response.")

                batch_assessments = list(structured.assessments)
                expected_ids = {
                    str(item.get("requirement", {}).get("id")) for item in batch
                }
                returned_ids = {
                    str(assessment.requirement_id) for assessment in batch_assessments
                }
                if returned_ids != expected_ids or len(batch_assessments) != len(
                    expected_ids
                ):
                    missing = sorted(expected_ids - returned_ids)
                    unexpected = sorted(returned_ids - expected_ids)
                    raise ValueError(
                        "Assessment IDs did not match the batch. "
                        f"Missing: {missing or 'none'}; "
                        f"unexpected: {unexpected or 'none'}."
                    )

                assessments_by_id = {
                    str(assessment.requirement_id): assessment
                    for assessment in batch_assessments
                }
                for item in batch:
                    requirement_id = str(item.get("requirement", {}).get("id"))
                    expected_test_ids = {
                        str(test.get("test_id"))
                        for test in item.get("linked_vplan_items", [])
                        if test.get("test_id") is not None
                    }
                    returned_test_ids = {
                        str(test_id)
                        for test_id in assessments_by_id[requirement_id].linked_tests
                    }
                    if returned_test_ids != expected_test_ids:
                        missing_tests = sorted(
                            expected_test_ids - returned_test_ids
                        )
                        unexpected_tests = sorted(
                            returned_test_ids - expected_test_ids
                        )
                        raise ValueError(
                            f"Assessment for {requirement_id} did not acknowledge "
                            "every linked vPlan item. "
                            f"Missing tests: {missing_tests or 'none'}; "
                            f"unexpected tests: {unexpected_tests or 'none'}."
                        )

                assessments.extend(batch_assessments)
                usage_records.append(
                    normalise_usage(
                        agent_name=f"{review_name}_batch_{batch_number}",
                        input_tokens=callback.prompt_tokens,
                        output_tokens=callback.completion_tokens,
                        total_tokens=callback.total_tokens,
                        total_cost=callback.total_cost,
                        model_name=model_name,
                    )
                )
                print(
                    f"[Coverage: {review_name}] Completed batch "
                    f"{batch_number}/{len(batches)} with "
                    f"{len(batch_assessments)} assessments."
                )
                completed = True
                break
            except Exception as error:
                if is_quota_exhausted(error):
                    quota_exhausted = True
                    print(
                        f"[Coverage: {review_name}] API quota is exhausted. "
                        "Stopping model calls; remaining mapped requirements will "
                        "be marked unclear. Deterministic coverage checks can continue."
                    )
                    break
                if attempt_number <= COVERAGE_MODEL_BATCH_RETRIES:
                    print(
                        f"[Coverage: {review_name}] Batch {batch_number}/{len(batches)} "
                        f"failed: {error}. Retrying."
                    )
                else:
                    print(
                        f"[Coverage: {review_name}] Batch {batch_number}/{len(batches)} "
                        f"failed after {attempt_number} attempts: {error}. "
                        "Affected requirements will be marked unclear."
                    )

        if not completed:
            failed_batches.append(batch_number)
            failed_requirement_ids.extend(
                str(item.get("requirement", {}).get("id")) for item in batch
            )

        if quota_exhausted:
            for remaining_number in range(batch_number + 1, len(batches) + 1):
                failed_batches.append(remaining_number)
                failed_requirement_ids.extend(
                    str(item.get("requirement", {}).get("id"))
                    for item in batches[remaining_number - 1]
                )
            break

    usage = aggregate_usage(*usage_records)
    usage.update(
        {
            "number_of_batches": len(batches),
            "batch_size": COVERAGE_MODEL_BATCH_SIZE,
            "failed_batches": failed_batches,
            "failed_requirement_ids": failed_requirement_ids,
            "quota_exhausted": quota_exhausted,
            "assessment_items_submitted": len(payloads),
            "vplan_items_submitted": len(submitted_test_ids),
            "test_ids_submitted": submitted_test_ids,
        }
    )
    return assessments, usage
