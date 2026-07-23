"""Multi-sample internal inconsistency analysis for one specification PDF."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from Backend.config import (
    INCONSISTENCY_AGENT_COUNT,
    INCONSISTENCY_MODEL,
    INCONSISTENCY_REPORT_DIR,
)

INCONSISTENCY_PROMPT = """
You are auditing a hardware specification for INTERNAL inconsistencies: cases
where two statements about the same entity cannot both be true simultaneously.

Compare statements referring to the same signal, register, field, opcode,
formula, encoding, state machine, or other named entity. Report only genuine
logical contradictions supported by two specific locations in the supplied
specification.

For each inconsistency:
1. Name the entity tying the statements together.
2. Identify exactly two conflicting statements. Report separate conflicting
   pairs separately.
3. Give the page and section, table, or paragraph identifier for both sides.
4. Quote briefly or closely paraphrase both statements.
5. Explain why both statements cannot be true.
6. Supply a short title and a category, such as Reserved Value Contradiction,
   Formula/Table Mismatch, Terminology Drift, Normative Conflict,
   Cross-Reference Error, or Enumeration Mismatch.
7. Set confidence to Low, Medium, or High. Use Low when the contradiction
   depends on inference rather than explicit conflicting text.

Do not report ambiguous wording, missing information, stylistic differences,
formatting differences, or clearly intentional reserved behaviour. Return no
finding unless both statements have source citations.
""".strip()


INCONSISTENCY_SCHEMA = {
    "type": "json_schema",
    "name": "specification_inconsistencies",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "inconsistencies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "entity": {"type": "string"},
                        "category": {"type": "string"},
                        "page_a": {"type": ["integer", "null"]},
                        "page_b": {"type": ["integer", "null"]},
                        "section_a": {"type": "string"},
                        "section_b": {"type": "string"},
                        "statement_a": {"type": "string"},
                        "statement_b": {"type": "string"},
                        "reason": {"type": "string"},
                        "confidence": {
                            "type": "string",
                            "enum": ["Low", "Medium", "High"],
                        },
                    },
                    "required": [
                        "title",
                        "entity",
                        "category",
                        "page_a",
                        "page_b",
                        "section_a",
                        "section_b",
                        "statement_a",
                        "statement_b",
                        "reason",
                        "confidence",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["inconsistencies"],
        "additionalProperties": False,
    },
}


CONFIDENCE_RANK = {"Low": 0, "Medium": 1, "High": 2}


def _normalise_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def normalise_finding_key(item: dict[str, Any]) -> tuple[Any, ...]:
    """Build an order-independent identity for one conflicting pair."""

    side_a = (
        item.get("page_a"),
        _normalise_text(item.get("section_a")),
    )
    side_b = (
        item.get("page_b"),
        _normalise_text(item.get("section_b")),
    )
    sides = tuple(
        sorted(
            (side_a, side_b),
            key=lambda side: (
                side[0] is None,
                -1 if side[0] is None else side[0],
                side[1],
            ),
        )
    )
    return (
        sides,
        _normalise_text(item.get("category")),
    )


def build_consensus(
    agent_results: list[list[dict[str, Any]]],
    *,
    majority_threshold: int,
) -> tuple[list[dict[str, Any]], int]:
    """Keep findings independently reported by the configured majority."""

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    vote_counter: Counter[tuple[Any, ...]] = Counter()

    for findings in agent_results:
        agent_keys: set[tuple[Any, ...]] = set()
        for finding in findings:
            key = normalise_finding_key(finding)
            grouped[key].append(finding)
            agent_keys.add(key)
        vote_counter.update(agent_keys)

    consensus = []
    for key, votes in vote_counter.items():
        if votes < majority_threshold:
            continue
        representative = dict(
            max(
                grouped[key],
                key=lambda item: CONFIDENCE_RANK.get(item.get("confidence", ""), -1),
            )
        )
        representative["agent_votes"] = votes
        consensus.append(representative)

    consensus.sort(
        key=lambda item: (
            -item["agent_votes"],
            -CONFIDENCE_RANK.get(item.get("confidence", ""), -1),
            item.get("page_a") is None,
            item.get("page_a") or 0,
            item.get("title", ""),
        )
    )
    return consensus, len(vote_counter)


def _usage_values(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def run_inconsistency_check(
    specification_pdf: str | Path,
    *,
    output_dir: str | Path = INCONSISTENCY_REPORT_DIR,
    model: str = INCONSISTENCY_MODEL,
    number_of_agents: int = INCONSISTENCY_AGENT_COUNT,
    client: OpenAI | None = None,
) -> dict[str, Any]:
    """Run independent PDF reviews and persist their majority consensus."""

    source_path = Path(specification_pdf)
    if source_path.suffix.casefold() != ".pdf" or not source_path.is_file():
        raise ValueError("A valid specification PDF is required.")
    if number_of_agents < 1:
        raise ValueError("number_of_agents must be at least 1.")

    majority_threshold = (number_of_agents // 2) + 1
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    api_client = client or OpenAI()
    uploaded_file_id: str | None = None
    agent_results: list[list[dict[str, Any]]] = []
    agent_output_paths: list[Path] = []
    failures: list[dict[str, Any]] = []
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    try:
        with source_path.open("rb") as source_file:
            uploaded = api_client.files.create(file=source_file, purpose="user_data")
        uploaded_file_id = uploaded.id

        for index in range(number_of_agents):
            agent_number = index + 1
            print(
                f"[Inconsistency check] Running reviewer "
                f"{agent_number}/{number_of_agents}."
            )
            try:
                response = api_client.responses.create(
                    model=model,
                    text={"format": INCONSISTENCY_SCHEMA},
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": INCONSISTENCY_PROMPT},
                                {"type": "input_file", "file_id": uploaded_file_id},
                            ],
                        }
                    ],
                )
                parsed = json.loads(response.output_text)
                findings = parsed.get("inconsistencies")
                if not isinstance(findings, list):
                    raise ValueError("Missing or malformed inconsistencies array.")

                agent_path = destination / (
                    f"inconsistency_{run_id}_reviewer_{agent_number}.json"
                )
                with agent_path.open("w", encoding="utf-8") as output_file:
                    json.dump(parsed, output_file, indent=2, ensure_ascii=False)
                agent_output_paths.append(agent_path)
                agent_results.append(findings)

                usage = _usage_values(response)
                for key in total_usage:
                    total_usage[key] += usage[key]
                print(
                    f"[Inconsistency check] Reviewer {agent_number} completed "
                    f"with {len(findings)} findings."
                )
            except Exception as error:
                failures.append({"reviewer": agent_number, "error": str(error)})
                print(f"[Inconsistency check] Reviewer {agent_number} failed: {error}")

        if len(agent_results) < majority_threshold:
            raise RuntimeError(
                "Too few reviewers completed successfully to establish the "
                f"configured majority ({len(agent_results)}/{majority_threshold})."
            )

        inconsistencies, unique_findings = build_consensus(
            agent_results,
            majority_threshold=majority_threshold,
        )
        report = {
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source_file": source_path.name,
                "model": model,
                "requested_reviewers": number_of_agents,
                "successful_reviewers": len(agent_results),
                "majority_threshold": majority_threshold,
                "unique_candidate_findings": unique_findings,
                "consensus_findings": len(inconsistencies),
                "failed_reviewers": failures,
                "usage": total_usage,
            },
            "inconsistencies": inconsistencies,
        }
        report_path = destination / f"inconsistency_consensus_{run_id}.json"
        with report_path.open("w", encoding="utf-8") as report_file:
            json.dump(report, report_file, indent=2, ensure_ascii=False)

        return {
            "report": report,
            "report_path": report_path,
            "reviewer_output_paths": agent_output_paths,
        }
    finally:
        if uploaded_file_id:
            try:
                api_client.files.delete(uploaded_file_id)
            except Exception as error:
                print(
                    "[Inconsistency check] Could not delete temporary uploaded "
                    f"file {uploaded_file_id}: {error}"
                )
