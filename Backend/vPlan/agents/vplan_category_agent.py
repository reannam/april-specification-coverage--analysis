from __future__ import annotations

import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter
from typing import Any

from langchain.agents import create_agent
from langchain_community.callbacks.manager import get_openai_callback

from Backend.vPlan.post_processing.usage_logger import normalise_usage
from Backend.vPlan.post_processing.vplan_metadata import build_vplan_metadata
from Backend.vPlan.pre_processing.data_class import CategorisedTests

CATEGORY_MODEL = os.getenv(
    "CATEGORY_MODEL",
    "openai:gpt-5.4-mini",
)
CATEGORY_BATCH_SIZE = max(
    1,
    int(os.getenv("CATEGORY_BATCH_SIZE", "24")),
)
CATEGORY_MAX_WORKERS = max(
    1,
    int(os.getenv("CATEGORY_MAX_WORKERS", "2")),
)
CATEGORY_BATCH_RETRIES = max(
    0,
    int(os.getenv("CATEGORY_BATCH_RETRIES", "1")),
)
REUSE_EXISTING_CATEGORIES = os.getenv(
    "REUSE_EXISTING_VPLAN_CATEGORIES",
    "true",
).lower() in {"1", "true", "yes", "on"}


CATEGORY_SYSTEM_PROMPT = """
You enrich verification-plan tests for a hardware engineer.

For every supplied test, assign exactly one concise category and one concise test name.

Rules:
- Return a category for every test_id.
- Copy every test_id exactly as supplied.
- Do not change, shorten, merge, or omit test IDs.
- Categories must contain one or two words.
- Use title case.
- Categorise according to the main behaviour being verified.
- Reuse an existing category when it accurately describes the test.
- Avoid near-duplicate categories.
- Do not use vague categories such as General, Other, Functional,
  Miscellaneous, Verification, or Protocol.
- Prefer a small, consistent category set.
- Aim for no more than 8 to 12 unique categories for the whole vPlan.
- Do not assign priorities.
- Derive test_name only from test_description and scenario_type.
- Test names must be 3 to 8 words, use title case, and describe the behaviour under test.
- Do not include the test ID, requirement ID, words such as "test case", or a trailing full stop.
"""


INVALID_EXISTING_CATEGORIES = {
    "",
    "uncategorised",
    "uncategorized",
    "general",
    "other",
    "miscellaneous",
    "verification",
    "protocol",
}


def normalise_category(category: str) -> str:
    cleaned = " ".join(str(category).strip().split())
    words = cleaned.split()

    if len(words) > 2:
        cleaned = " ".join(words[:2])

    return cleaned.title() or "Uncategorised"


def _title_word(word: str) -> str:
    """Keep signal names and acronyms readable while title-casing ordinary words."""

    if any(character.isdigit() for character in word) or word.isupper():
        return word

    return word.capitalize()


def normalise_test_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\- /]", "", str(name or "")).strip(" .-_/")
    words = cleaned.split()
    return " ".join(_title_word(word) for word in words[:8])


def is_identifier_like_test_name(name: str, test: dict) -> bool:
    """Reject test IDs that a model has copied into the human-readable name."""

    normalised_name = normalise_test_name(name).casefold()
    known_identifiers = {
        str(test.get(key, "")).strip().casefold()
        for key in ("test_id", "requirement_id")
        if test.get(key)
    }

    return normalised_name in known_identifiers or bool(
        re.match(r"^(?:tc|test)[ _-]?(?:req|case|id)(?:[ _-]|$)", normalised_name)
    )


def deterministic_test_name(test: dict) -> str:
    """Create a stable fallback name directly from the test description."""

    description = re.sub(
        r"^(verify|check|confirm|ensure|validate|test)(?:\s+that)?\s+",
        "",
        str(test.get("test_description", "")).strip(),
        flags=re.IGNORECASE,
    )
    fallback = normalise_test_name(description)

    if fallback:
        return fallback

    return f"{str(test.get('scenario_type', 'Verification')).title()} Verification"


def has_usable_category(test: dict) -> bool:
    category = normalise_category(str(test.get("category", "")))
    return category.casefold() not in INVALID_EXISTING_CATEGORIES


def has_usable_test_name(test: dict) -> bool:
    name = normalise_test_name(str(test.get("test_name", "")))
    return len(name.split()) >= 2 and not is_identifier_like_test_name(name, test)


def is_uncovered_traceability_row(test: dict) -> bool:
    return str(test.get("coverage", "")).strip().lower() == "uncovered"


def validate_tests(tests: Any) -> list[dict]:
    if not isinstance(tests, list):
        raise ValueError("The vPlan must contain a 'feature_list' array.")

    if not tests:
        raise ValueError("The vPlan contains no tests to categorise.")

    missing_indexes = [
        index
        for index, test in enumerate(tests)
        if not isinstance(test, dict) or not test.get("test_id")
    ]

    if missing_indexes:
        raise ValueError(
            "Every vPlan test must contain a test_id. "
            "Missing at indexes: " + ", ".join(str(index) for index in missing_indexes)
        )

    return tests


def normalise_for_fingerprint(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip().casefold(),
    )


def test_fingerprint(test: dict) -> str:
    """Group exact duplicate categorisation tasks together."""

    return "|".join(
        [
            normalise_for_fingerprint(test.get("scenario_type")),
            normalise_for_fingerprint(test.get("test_description")),
        ]
    )


def build_unique_tasks(
    tests: list[dict],
) -> tuple[list[dict], dict[str, list[str]]]:
    """Enrich identical scenarios once, then copy that result to duplicate rows."""

    representative_by_fingerprint: dict[str, dict] = {}
    ids_by_representative: dict[str, list[str]] = {}

    for test in tests:
        test_id = str(test["test_id"])
        fingerprint = test_fingerprint(test)

        if fingerprint not in representative_by_fingerprint:
            representative_by_fingerprint[fingerprint] = {
                "test_id": test_id,
                "requirement_id": test.get("requirement_id"),
                "scenario_type": test.get("scenario_type"),
                "test_description": test.get("test_description"),
                "category": test.get("category"),
            }
            ids_by_representative[test_id] = []

        representative_id = str(representative_by_fingerprint[fingerprint]["test_id"])
        ids_by_representative[representative_id].append(test_id)

    return (
        list(representative_by_fingerprint.values()),
        ids_by_representative,
    )


def split_batches(items: list[dict]) -> list[list[dict]]:
    return [
        items[index : index + CATEGORY_BATCH_SIZE]
        for index in range(0, len(items), CATEGORY_BATCH_SIZE)
    ]


def create_category_agent():
    return create_agent(
        model=CATEGORY_MODEL,
        response_format=CategorisedTests,
        system_prompt=CATEGORY_SYSTEM_PROMPT,
    )


def categorise_batch_once(
    *,
    batch: list[dict],
    batch_number: int,
    category_hints: list[str],
) -> tuple[dict[str, dict[str, str]], dict, str]:
    expected_ids = {str(test["test_id"]) for test in batch}

    hints_text = (
        ", ".join(category_hints)
        if category_hints
        else "No categories have been established yet."
    )

    run_id = uuid.uuid4()
    agent = create_category_agent()

    with get_openai_callback() as callback:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Categorise every test in this batch.\n\n"
                            "Preferred categories already used in this "
                            "vPlan:\n"
                            f"{hints_text}\n\n"
                            "Reuse those categories where suitable. "
                            "Return exactly one result for every test_id "
                            "and copy each test_id exactly.\n\n"
                            + json.dumps(
                                batch,
                                separators=(",", ":"),
                                ensure_ascii=False,
                            )
                        ),
                    }
                ]
            },
            config={
                "run_id": run_id,
                "run_name": ("vplan_category_generation_" f"batch_{batch_number}"),
                "metadata": {
                    "ls_provider": "openai",
                    "ls_model_name": CATEGORY_MODEL.removeprefix("openai:"),
                    "batch_number": batch_number,
                    "number_of_tests": len(batch),
                },
                "tags": [
                    "vplan-category-agent",
                    "vplan-post-processing",
                    "batched-category-generation",
                ],
            },
        )

        structured = result.get("structured_response")

        if structured is None:
            raise ValueError(
                f"Category batch {batch_number} did not return "
                "a structured response."
            )

        usage = normalise_usage(
            agent_name="vplan_category_agent",
            input_tokens=callback.prompt_tokens,
            output_tokens=callback.completion_tokens,
            total_tokens=callback.total_tokens,
            total_cost=callback.total_cost,
            model_name=CATEGORY_MODEL.removeprefix("openai:"),
        )

    enrichments: dict[str, dict[str, str]] = {}

    tests_by_id = {str(test["test_id"]): test for test in batch}

    for item in structured.tests:
        test_id = str(item.test_id)

        if test_id not in expected_ids:
            continue

        source_test = tests_by_id[test_id]
        generated_name = normalise_test_name(item.test_name)
        if not has_usable_test_name({**source_test, "test_name": generated_name}):
            generated_name = deterministic_test_name(source_test)
            print(
                f"Enrichment agent returned an unusable name for {test_id}; "
                "using the deterministic description-based name."
            )

        enrichments[test_id] = {
            "category": normalise_category(item.category),
            "test_name": generated_name,
        }

    return enrichments, usage, str(run_id)


def categorise_batch_with_retries(
    *,
    batch: list[dict],
    batch_number: int,
    category_hints: list[str],
) -> tuple[dict[str, dict[str, str]], list[dict], list[str]]:
    remaining = list(batch)
    enrichments: dict[str, dict[str, str]] = {}
    usage_records: list[dict] = []
    trace_ids: list[str] = []

    for attempt in range(CATEGORY_BATCH_RETRIES + 1):
        if not remaining:
            break

        try:
            returned, usage, trace_id = categorise_batch_once(
                batch=remaining,
                batch_number=batch_number,
                category_hints=category_hints,
            )
            enrichments.update(returned)
            usage_records.append(usage)
            trace_ids.append(trace_id)

        except Exception as error:
            print(
                f"Category batch {batch_number}, attempt "
                f"{attempt + 1} failed: {error}"
            )

        remaining = [
            test for test in remaining if str(test["test_id"]) not in enrichments
        ]

        if remaining and attempt < CATEGORY_BATCH_RETRIES:
            print(
                f"Category batch {batch_number} omitted "
                f"{len(remaining)} tests. Retrying only "
                "the missing tests."
            )

    for test in remaining:
        test_id = str(test["test_id"])
        enrichments[test_id] = {
            "category": normalise_category(str(test.get("category", ""))),
            "test_name": deterministic_test_name(test),
        }
        print(
            f"Enrichment agent repeatedly omitted {test_id}; using deterministic defaults."
        )

    return enrichments, usage_records, trace_ids


def combine_usage_records(records: list[dict]) -> dict:
    return normalise_usage(
        agent_name="vplan_category_agent",
        input_tokens=sum(
            int(record.get("prompt_tokens", 0) or 0) for record in records
        ),
        output_tokens=sum(
            int(record.get("completion_tokens", 0) or 0) for record in records
        ),
        total_tokens=sum(int(record.get("total_tokens", 0) or 0) for record in records),
        total_cost=sum(float(record.get("total_cost", 0) or 0) for record in records),
        model_name=CATEGORY_MODEL.removeprefix("openai:"),
    )


def categorise_vplan(
    vplan_file: str | Path,
    requirements_file: str | Path,
) -> tuple[Path, dict, str]:
    started = perf_counter()

    vplan_path = Path(vplan_file).resolve()
    requirements_path = Path(requirements_file).resolve()

    if not vplan_path.exists():
        raise ValueError(f"vPlan file does not exist: {vplan_path}")

    if not requirements_path.exists():
        raise ValueError("Requirements file does not exist: " f"{requirements_path}")

    with vplan_path.open("r", encoding="utf-8") as file:
        vplan = json.load(file)

    if not isinstance(vplan, dict):
        raise ValueError("The vPlan file must contain a JSON object.")

    tests = validate_tests(vplan.get("feature_list"))

    enrichments_by_test_id: dict[str, dict[str, str]] = {}

    if REUSE_EXISTING_CATEGORIES:
        for test in tests:
            if has_usable_category(test) and has_usable_test_name(test):
                enrichments_by_test_id[str(test["test_id"])] = {
                    "category": normalise_category(str(test["category"])),
                    "test_name": normalise_test_name(str(test["test_name"])),
                }

    tests_needing_enrichment = [
        test
        for test in tests
        if str(test["test_id"]) not in enrichments_by_test_id
        and not is_uncovered_traceability_row(test)
    ]

    usage_records: list[dict] = []
    trace_ids: list[str] = []

    if tests_needing_enrichment:
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not found. Check your .env file.")

        unique_tasks, ids_by_representative = build_unique_tasks(
            tests_needing_enrichment
        )
        batches = split_batches(unique_tasks)

        print(
            f"Enriching {len(tests_needing_enrichment)} tests "
            f"as {len(unique_tasks)} unique tasks across "
            f"{len(batches)} batches."
        )

        representative_enrichments: dict[str, dict[str, str]] = {}
        existing_hints = sorted(
            {item["category"] for item in enrichments_by_test_id.values()}
            | {
                normalise_category(str(test.get("category", "")))
                for test in tests
                if has_usable_category(test)
            }
        )

        # Process the first batch synchronously to establish a shared category
        # vocabulary before the remaining independent batches run concurrently.
        first_enrichments, first_usage, first_traces = categorise_batch_with_retries(
            batch=batches[0],
            batch_number=1,
            category_hints=existing_hints,
        )
        representative_enrichments.update(first_enrichments)
        usage_records.extend(first_usage)
        trace_ids.extend(first_traces)

        category_hints = sorted(
            set(existing_hints)
            | {
                item["category"]
                for item in first_enrichments.values()
                if item["category"] != "Uncategorised"
            }
        )

        remaining_batches = batches[1:]

        if remaining_batches:
            max_workers = min(
                CATEGORY_MAX_WORKERS,
                len(remaining_batches),
            )

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        categorise_batch_with_retries,
                        batch=batch,
                        batch_number=batch_number,
                        category_hints=category_hints,
                    ): batch_number
                    for batch_number, batch in enumerate(
                        remaining_batches,
                        start=2,
                    )
                }

                for future in as_completed(futures):
                    batch_number = futures[future]

                    try:
                        batch_enrichments, batch_usage, batch_traces = future.result()
                    except Exception as error:
                        print(
                            f"Category batch {batch_number} failed "
                            f"unexpectedly: {error}"
                        )
                        batch = remaining_batches[batch_number - 2]
                        batch_enrichments = {
                            str(test["test_id"]): {
                                "category": normalise_category(
                                    str(test.get("category", ""))
                                ),
                                "test_name": deterministic_test_name(test),
                            }
                            for test in batch
                        }
                        batch_usage = []
                        batch_traces = []

                    representative_enrichments.update(batch_enrichments)
                    usage_records.extend(batch_usage)
                    trace_ids.extend(batch_traces)

        for representative_id, related_ids in ids_by_representative.items():
            representative = representative_enrichments.get(
                representative_id,
                {},
            )

            for test_id in related_ids:
                enrichments_by_test_id[test_id] = representative

    expected_ids = {str(test["test_id"]) for test in tests}

    tests_by_id = {str(test["test_id"]): test for test in tests}

    for missing_id in expected_ids - set(enrichments_by_test_id):
        test = tests_by_id[missing_id]
        enrichments_by_test_id[missing_id] = {
            "category": normalise_category(str(test.get("category", ""))),
            "test_name": deterministic_test_name(test),
        }

    for test in tests:
        test_id = str(test["test_id"])

        if is_uncovered_traceability_row(test):
            test["category"] = "Uncategorised"
            test["test_name"] = ""
            test["priority"] = 3
            test["test_description"] = ""
            test["test_steps"] = []
            test["expected_results"] = []
            continue

        enrichment = enrichments_by_test_id[test_id]
        test["category"] = enrichment.get("category") or normalise_category(
            str(test.get("category", ""))
        )
        test["test_name"] = enrichment.get("test_name") or deterministic_test_name(test)
        test["priority"] = 3

    vplan["metadata"] = build_vplan_metadata(
        requirements_file=requirements_path,
        existing_metadata=vplan.get("metadata", {}),
    )

    with vplan_path.open("w", encoding="utf-8") as file:
        json.dump(
            vplan,
            file,
            indent=2,
            ensure_ascii=False,
        )

    usage = combine_usage_records(usage_records)
    elapsed = perf_counter() - started

    print(f"Enriched {len(tests)} vPlan tests in " f"{elapsed:.2f} seconds.")

    return vplan_path, usage, ",".join(trace_ids)
