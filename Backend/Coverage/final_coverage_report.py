from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from Backend.config import COVERAGE_TERMS_FILE, FINAL_COVERAGE_DIR
from Backend.text_config import load_grouped_text_config, require_groups

TERM_GROUPS, _ = load_grouped_text_config(COVERAGE_TERMS_FILE)
require_groups(
    TERM_GROUPS,
    {
        "covered_statuses",
        "partially_covered_statuses",
        "ambiguous_statuses",
        "not_covered_statuses",
        "traceability_fields",
    },
    source=COVERAGE_TERMS_FILE,
)

COVERED_STATUSES = TERM_GROUPS["covered_statuses"]
PARTIAL_STATUSES = TERM_GROUPS["partially_covered_statuses"]
UNCOVERED_STATUSES = TERM_GROUPS["not_covered_statuses"]
AMBIGUOUS_STATUSES = TERM_GROUPS["ambiguous_statuses"]
TRACEABILITY_FIELDS = TERM_GROUPS["traceability_fields"]

# These are deliberately transparent policy weights rather than inferred risk or
# priority values. The final report exposes each per-requirement contribution.
STATUS_SCORE = {
    "Covered": 1.0,
    "Partially covered": 0.5,
    "Uncovered": 0.0,
    "Ambiguous / not yet plannable": 0.0,
}


def load_json(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    return path


def extract_vplan_items(
    vplan_data: dict[str, Any] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(vplan_data, list):
        return vplan_data

    if isinstance(vplan_data.get("feature_list"), list):
        return vplan_data["feature_list"]

    if isinstance(vplan_data.get("table"), dict):
        feature_list = vplan_data["table"].get("feature_list")
        if isinstance(feature_list, list):
            return feature_list

    if isinstance(vplan_data.get("vplan"), list):
        return vplan_data["vplan"]

    raise ValueError(
        "Could not find vPlan items. Expected 'feature_list', 'table.feature_list', or 'vplan'."
    )


def normalise_status(status: str | None) -> str:
    normalised = str(status or "").strip().casefold()

    if normalised in COVERED_STATUSES:
        return "Covered"

    if normalised in PARTIAL_STATUSES:
        return "Partially covered"

    if normalised in AMBIGUOUS_STATUSES:
        return "Ambiguous / not yet plannable"

    return "Uncovered"


def get_requirement_id(item: dict[str, Any]) -> str | None:
    requirement_id = item.get("id") or item.get("requirement_id")

    if requirement_id is None:
        return None

    return str(requirement_id)


def get_vplan_requirement_id(item: dict[str, Any]) -> str | None:
    requirement_id = item.get("requirement_id") or item.get("id")

    if requirement_id is None:
        return None

    return str(requirement_id)


def calculate_requirement_mapping_coverage(
    spec_requirements: list[dict[str, Any]],
    vplan_items: list[dict[str, Any]],
) -> dict[str, Any]:
    total_spec_items = len(spec_requirements)

    vplan_requirement_ids = {
        get_vplan_requirement_id(item)
        for item in vplan_items
        if get_vplan_requirement_id(item)
    }

    mapped = []
    unmapped = []

    for requirement in spec_requirements:
        requirement_id = get_requirement_id(requirement)

        item = {
            "requirement_id": requirement_id,
            "source_section": requirement.get("source_section"),
            "text": requirement.get("text"),
        }

        if requirement_id in vplan_requirement_ids:
            mapped.append(item)
        else:
            unmapped.append(item)

    mapped_count = len(mapped)

    return {
        "total_spec_items": total_spec_items,
        "spec_items_mapped_to_vplan": mapped_count,
        "spec_items_unmapped_to_vplan": len(unmapped),
        "requirement_mapping_coverage": (
            round((mapped_count / total_spec_items) * 100, 2)
            if total_spec_items
            else 0.0
        ),
        "unmapped_requirements": unmapped,
    }


def calculate_weighted_coverage(
    labelled_requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    total_items = len(labelled_requirements)

    rows = []
    weighted_score = 0.0

    for requirement in labelled_requirements:
        status = normalise_status(requirement.get("verified_coverage_status"))
        coverage_score = STATUS_SCORE[status]

        weighted_score += coverage_score

        rows.append(
            {
                "requirement_id": get_requirement_id(requirement),
                "status": status,
                "coverage_score": coverage_score,
            }
        )

    return {
        "formula": "sum(c_i) / N * 100, where c_i ∈ {1, 0.5, 0}",
        "total_items": total_items,
        "weighted_score": weighted_score,
        "weighted_coverage": (
            round((weighted_score / total_items) * 100, 2) if total_items else 0.0
        ),
        "rows": rows,
    }


def calculate_traceability_coverage(
    vplan_items: list[dict[str, Any]],
) -> dict[str, Any]:
    total_vplan_items = len(vplan_items)

    traceable = []
    untraceable = []

    for index, item in enumerate(vplan_items):
        test_id = item.get("test_id") or item.get("id") or f"VPLAN_ITEM_{index + 1:03d}"

        has_trace = any(
            field in item and item.get(field) not in [None, "", []]
            for field in TRACEABILITY_FIELDS
        )

        summary = {
            "vplan_index": index,
            "test_id": test_id,
            "requirement_id": item.get("requirement_id"),
        }

        if has_trace:
            traceable.append(summary)
        else:
            untraceable.append(summary)

    return {
        "total_vplan_items": total_vplan_items,
        "vplan_items_with_source_trace": len(traceable),
        "vplan_items_without_source_trace": len(untraceable),
        "traceability_coverage": (
            round((len(traceable) / total_vplan_items) * 100, 2)
            if total_vplan_items
            else 0.0
        ),
        "untraceable_items": untraceable,
    }


def calculate_orphan_rate(
    spec_requirements: list[dict[str, Any]],
    vplan_items: list[dict[str, Any]],
) -> dict[str, Any]:
    spec_requirement_ids = {
        get_requirement_id(requirement)
        for requirement in spec_requirements
        if get_requirement_id(requirement)
    }

    total_vplan_items = len(vplan_items)

    linked = []
    orphan = []

    for index, item in enumerate(vplan_items):
        test_id = item.get("test_id") or item.get("id") or f"VPLAN_ITEM_{index + 1:03d}"
        requirement_id = get_vplan_requirement_id(item)

        summary = {
            "vplan_index": index,
            "test_id": test_id,
            "requirement_id": requirement_id,
            "test_description": item.get("test_description"),
        }

        if requirement_id in spec_requirement_ids:
            linked.append(summary)
        else:
            orphan.append(summary)

    return {
        "total_vplan_items": total_vplan_items,
        "vplan_items_with_source_in_spec": len(linked),
        "orphan_vplan_items": len(orphan),
        "orphan_rate": (
            round((len(orphan) / total_vplan_items) * 100, 2)
            if total_vplan_items
            else 0.0
        ),
        "orphan_items": orphan,
    }


def calculate_testability_from_coverage_status(
    labelled_requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Deterministic fallback testability summary.

    This uses the coverage verifier output:
    - Covered and Partially covered count as testable mapped entries.
    - Uncovered and Ambiguous do not count as testable.
    """

    mapped_items = []
    testable_items = []
    not_testable_items = []

    for requirement in labelled_requirements:
        linked_tests = requirement.get("linked_tests", [])
        status = normalise_status(requirement.get("verified_coverage_status"))

        if not linked_tests:
            continue

        item = {
            "requirement_id": get_requirement_id(requirement),
            "status": status,
            "linked_tests": linked_tests,
            "reason": requirement.get("coverage_verification_reason"),
        }

        mapped_items.append(item)

        if status in {"Covered", "Partially covered"}:
            testable_items.append(item)
        else:
            not_testable_items.append(item)

    mapped_count = len(mapped_items)
    testable_count = len(testable_items)

    return {
        "mapped_spec_items": mapped_count,
        "mapped_items_with_testable_vplan_entry": testable_count,
        "mapped_items_without_testable_vplan_entry": len(not_testable_items),
        "testability_coverage": (
            round((testable_count / mapped_count) * 100, 2) if mapped_count else 0.0
        ),
        "not_testable_items": not_testable_items,
    }


def build_coverage_summary(
    spec_requirements: list[dict[str, Any]],
    labelled_requirements: list[dict[str, Any]],
    orphan_result: dict[str, Any],
) -> dict[str, Any]:
    counts = {
        "covered": 0,
        "partially_covered": 0,
        "uncovered": 0,
        "ambiguity_uncovered": 0,
    }

    for requirement in labelled_requirements:
        status = normalise_status(requirement.get("verified_coverage_status"))

        if status == "Covered":
            counts["covered"] += 1
        elif status == "Partially covered":
            counts["partially_covered"] += 1
        elif status == "Ambiguous / not yet plannable":
            counts["ambiguity_uncovered"] += 1
        else:
            counts["uncovered"] += 1

    return {
        "total_spec_items": len(spec_requirements),
        "covered": counts["covered"],
        "partially_covered": counts["partially_covered"],
        "uncovered": counts["uncovered"],
        "ambiguity_uncovered": counts["ambiguity_uncovered"],
        "orphan_vplan_items": orphan_result["orphan_vplan_items"],
    }


def build_gap_report(
    labelled_requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gap_rows = []

    for requirement in labelled_requirements:
        status = normalise_status(requirement.get("verified_coverage_status"))

        if status == "Covered":
            continue

        gap_rows.append(
            {
                "requirement_id": get_requirement_id(requirement),
                "source_section": requirement.get("source_section"),
                "coverage_status": status,
                "spec_statement": requirement.get("text"),
                "linked_vplan_items": requirement.get("linked_tests", []),
                "reason": requirement.get("coverage_verification_reason"),
            }
        )

    return gap_rows


def build_ambiguity_report(
    labelled_requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ambiguity_rows = []

    for requirement in labelled_requirements:
        status = normalise_status(requirement.get("verified_coverage_status"))
        linked_edge_cases = requirement.get("linked_edge_cases", [])
        linked_weak_word_flags = requirement.get("linked_weak_word_flags", [])

        has_ambiguity_evidence = bool(linked_edge_cases) or bool(linked_weak_word_flags)

        if status != "Ambiguous / not yet plannable" and not has_ambiguity_evidence:
            continue

        ambiguity_rows.append(
            {
                "requirement_id": get_requirement_id(requirement),
                "source_section": requirement.get("source_section"),
                "coverage_status": status,
                "spec_statement": requirement.get("text"),
                "linked_tests": requirement.get("linked_tests", []),
                "reason": requirement.get("coverage_verification_reason"),
                "linked_edge_cases": linked_edge_cases,
                "linked_weak_word_flags": linked_weak_word_flags,
            }
        )

    return ambiguity_rows


def build_final_coverage_report(
    spec_file: str | Path,
    vplan_file: str | Path,
    coverage_file: str | Path,
) -> dict[str, Any]:
    spec_data = load_json(spec_file)
    vplan_data = load_json(vplan_file)
    coverage_data = load_json(coverage_file)

    spec_requirements = spec_data.get("requirements", [])
    labelled_requirements = coverage_data.get("labelled_requirements", [])
    vplan_items = extract_vplan_items(vplan_data)

    if not isinstance(spec_requirements, list):
        raise ValueError("Spec JSON must contain a top-level 'requirements' list.")

    if not isinstance(labelled_requirements, list):
        raise ValueError(
            "Coverage JSON must contain a top-level 'labelled_requirements' list."
        )

    mapping_result = calculate_requirement_mapping_coverage(
        spec_requirements=spec_requirements,
        vplan_items=vplan_items,
    )

    weighted_result = calculate_weighted_coverage(labelled_requirements)

    traceability_result = calculate_traceability_coverage(vplan_items)

    orphan_result = calculate_orphan_rate(
        spec_requirements=spec_requirements,
        vplan_items=vplan_items,
    )

    testability_result = calculate_testability_from_coverage_status(
        labelled_requirements
    )

    coverage_summary = build_coverage_summary(
        spec_requirements=spec_requirements,
        labelled_requirements=labelled_requirements,
        orphan_result=orphan_result,
    )

    coverage_percentages = {
        "requirement_mapping_coverage": mapping_result["requirement_mapping_coverage"],
        "weighted_coverage": weighted_result["weighted_coverage"],
        "traceability_coverage": traceability_result["traceability_coverage"],
        "testability_coverage": testability_result["testability_coverage"],
        "orphan_rate": orphan_result["orphan_rate"],
    }

    gap_report = build_gap_report(labelled_requirements)
    ambiguity_report = build_ambiguity_report(labelled_requirements)

    return {
        "metadata": {
            "date_created": datetime.now().strftime("%B %d %Y"),
            "time_created": datetime.now().strftime("%I:%M%p").lower(),
            "spec_file": str(spec_file),
            "vplan_file": str(vplan_file),
            "coverage_file": str(coverage_file),
        },
        "coverage_summary": coverage_summary,
        "coverage_percentages": coverage_percentages,
        "gap_report": gap_report,
        "ambiguity_report": ambiguity_report,
        "supporting_metrics": {
            "requirement_mapping": mapping_result,
            "weighted_coverage": weighted_result,
            "traceability": traceability_result,
            "testability": testability_result,
            "orphan_rate": orphan_result,
        },
    }


def write_final_outputs(
    report: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    summary_file = save_json(
        {
            "metadata": report["metadata"],
            "coverage_summary": report["coverage_summary"],
            "coverage_percentages": report["coverage_percentages"],
        },
        output_path / "coverage_summary.json",
    )

    gap_file = save_json(
        {
            "metadata": report["metadata"],
            "gap_report": report["gap_report"],
        },
        output_path / "gap_report.json",
    )

    ambiguity_file = save_json(
        {
            "metadata": report["metadata"],
            "ambiguity_report": report["ambiguity_report"],
        },
        output_path / "ambiguity_report.json",
    )

    full_report_file = save_json(
        report,
        output_path / "final_coverage_report.json",
    )

    return {
        "coverage_summary_file": str(summary_file),
        "gap_report_file": str(gap_file),
        "ambiguity_report_file": str(ambiguity_file),
        "final_coverage_report_file": str(full_report_file),
    }


def print_final_report_summary(
    report: dict[str, Any], output_files: dict[str, str]
) -> None:
    print("\nFinal Coverage Report")
    print("---------------------")

    summary = report["coverage_summary"]
    percentages = report["coverage_percentages"]

    print("\nA. Coverage summary")
    print(f"Total spec items:        {summary['total_spec_items']}")
    print(f"Covered:                 {summary['covered']}")
    print(f"Partially covered:       {summary['partially_covered']}")
    print(f"Uncovered:               {summary['uncovered']}")
    print(f"Ambiguity-uncovered:     {summary['ambiguity_uncovered']}")
    print(f"Orphan vPlan items:      {summary['orphan_vplan_items']}")

    print("\nB. Coverage percentages")
    print(f"Requirement mapping:     {percentages['requirement_mapping_coverage']}%")
    print(f"Weighted coverage:       {percentages['weighted_coverage']}%")
    print(f"Traceability coverage:   {percentages['traceability_coverage']}%")
    print(f"Testability coverage:    {percentages['testability_coverage']}%")
    print(f"Orphan rate:             {percentages['orphan_rate']}%")

    print("\nC. Gap report")
    print(f"Gap items:               {len(report['gap_report'])}")

    print("\nD. Ambiguity report")
    print(f"Ambiguity items:         {len(report['ambiguity_report'])}")

    print("\nOutput files")
    for label, path in output_files.items():
        print(f"{label}: {path}")


def run_final_coverage_report(
    spec_file: str | Path,
    vplan_file: str | Path,
    coverage_file: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    report = build_final_coverage_report(
        spec_file=spec_file,
        vplan_file=vplan_file,
        coverage_file=coverage_file,
    )

    output_files = write_final_outputs(
        report=report,
        output_dir=output_dir,
    )

    print_final_report_summary(report, output_files)

    return {
        "report": report,
        "output_files": output_files,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create final coverage summary, gap report, and ambiguity report files."
    )

    parser.add_argument(
        "--spec-file",
        required=True,
        help="Path to the extracted spec JSON file.",
    )

    parser.add_argument(
        "--vplan-file",
        required=True,
        help="Path to the generated vPlan JSON file.",
    )

    parser.add_argument(
        "--coverage-file",
        required=True,
        help="Path to the output JSON from coverage_status_verifier.py.",
    )

    parser.add_argument(
        "--output-dir",
        default=str(FINAL_COVERAGE_DIR),
        help="Directory where final report files should be written.",
    )

    args = parser.parse_args()

    run_final_coverage_report(
        spec_file=args.spec_file,
        vplan_file=args.vplan_file,
        coverage_file=args.coverage_file,
        output_dir=args.output_dir,
    )
