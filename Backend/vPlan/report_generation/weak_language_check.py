from datetime import datetime
import json
import re
from pathlib import Path

from Backend.config import WEAK_LANGUAGE_DIR, WEAK_LANGUAGE_TERMS_FILE
from Backend.text_config import load_grouped_text_config, require_groups

TERM_GROUPS, _ = load_grouped_text_config(WEAK_LANGUAGE_TERMS_FILE)
require_groups(
    TERM_GROUPS,
    {"strong_requirement_words", "weak_requirement_words"},
    source=WEAK_LANGUAGE_TERMS_FILE,
)
STRONG_REQUIREMENT_WORDS = TERM_GROUPS["strong_requirement_words"]
WEAK_REQUIREMENT_WORDS = TERM_GROUPS["weak_requirement_words"]


def unwrap_requirements(data) -> list[dict]:
    """Accept either a raw requirements list or a wrapped requirements object."""

    if isinstance(data, dict):
        data = data.get("requirements", [])

    if not isinstance(data, list):
        raise ValueError(
            "Expected requirements to be a list, or a dict containing "
            "a 'requirements' list."
        )

    return data


def get_requirement_display_text(requirement: dict) -> str:
    """Return the exact original requirement wording without lowercasing it."""

    parts: list[str] = []

    for key in ("text", "description"):
        value = str(requirement.get(key, "") or "").strip()

        if value and value not in parts:
            parts.append(value)

    return " ".join(parts)


def get_requirement_source_section(requirement: dict) -> str | None:
    """Return the source section, deriving it from the requirement ID if needed."""

    explicit_section = (
        requirement.get("source_section")
        or requirement.get("section")
        or requirement.get("chapter")
    )

    if explicit_section:
        return str(explicit_section)

    requirement_id = str(requirement.get("id", ""))
    match = re.search(
        r"REQ_([A-Z]+\d+(?:_\d+)*)",
        requirement_id,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(1).replace("_", ".").upper()


def _term_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term.strip())
    return re.compile(
        rf"(?<!\w){escaped}(?!\w)",
        flags=re.IGNORECASE,
    )


def find_matching_terms(
    text: str,
    words_or_phrases: list[str],
) -> list[str]:
    """Return exact matched terms, preferring longer phrases first."""

    matches: list[str] = []

    unique_terms = sorted(
        {term.strip().lower() for term in words_or_phrases if term.strip()},
        key=lambda term: (-len(term), term),
    )

    for term in unique_terms:
        if _term_pattern(term).search(text):
            matches.append(term)

    return matches


def contains_word_or_phrase(
    text: str,
    words_or_phrases: list[str],
) -> bool:
    return bool(find_matching_terms(text, words_or_phrases))


def check_requirement_language(requirements) -> list[dict]:
    """Check requirements and include exact source wording in every issue."""

    requirements = unwrap_requirements(requirements)
    issues: list[dict] = []

    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue

        requirement_id = str(requirement.get("id", "UNKNOWN"))
        requirement_text = get_requirement_display_text(requirement)
        searchable_text = requirement_text.lower()
        source_section = get_requirement_source_section(requirement)

        strong_matches = find_matching_terms(
            searchable_text,
            STRONG_REQUIREMENT_WORDS,
        )
        weak_matches = find_matching_terms(
            searchable_text,
            WEAK_REQUIREMENT_WORDS,
        )

        shared_fields = {
            "requirement_id": requirement_id,
            "requirement_text": requirement_text,
            "source_section": source_section,
        }

        if weak_matches:
            issues.append(
                {
                    **shared_fields,
                    "issue_type": "weak_or_optional_language",
                    "matched_words": weak_matches,
                    "message": (
                        "Requirement contains weak or optional wording. "
                        "Do not infer mandatory behaviour unless it is "
                        "explicitly stated."
                    ),
                }
            )

        if not strong_matches:
            issues.append(
                {
                    **shared_fields,
                    "issue_type": "missing_strong_requirement_language",
                    "matched_words": [],
                    "message": (
                        "Requirement does not contain strong requirement "
                        "wording such as must, shall, should, required, "
                        "or requires."
                    ),
                }
            )

    return issues


def save_requirement_language_report(
    issues: list[dict],
    output_file: str | Path,
    source_file: str | Path | None = None,
) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "number_of_language_issues": len(issues),
        "source_file": Path(source_file).name if source_file else None,
        "issues": issues,
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Requirement language report saved to {output_path}")


def print_requirement_language_summary(issues: list[dict]) -> None:
    print("\nRequirement language check")
    print("--------------------------")
    print(f"Language issues found: {len(issues)}")

    if not issues:
        print("No weak or unclear requirement language found.")
        return

    display_limit = 50

    for issue in issues[:display_limit]:
        requirement_id = issue["requirement_id"]
        issue_type = issue["issue_type"]

        if issue_type == "weak_or_optional_language":
            matched_words = ", ".join(issue.get("matched_words", []))
            print(f"- {requirement_id}: weak language found ({matched_words})")
        else:
            print(f"- {requirement_id}: missing strong requirement language")

    remaining = len(issues) - display_limit
    if remaining > 0:
        print(f"... {remaining} additional language issues saved to the JSON report.")


def get_flagged_requirements(
    requirements,
    language_issues: list[dict],
) -> list[dict]:
    requirements = unwrap_requirements(requirements)
    flagged_ids = {str(issue["requirement_id"]) for issue in language_issues}

    return [
        requirement
        for requirement in requirements
        if str(requirement.get("id")) in flagged_ids
    ]


def run_weak_language_checker(requirements_file: str) -> Path:
    print(f"Using requirements file: {requirements_file}")

    with open(requirements_file, "r", encoding="utf-8") as file:
        input_data = json.load(file)

    input_requirements = unwrap_requirements(input_data)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    weak_language_file = WEAK_LANGUAGE_DIR / f"weak_words_{timestamp}.json"

    issues = check_requirement_language(input_requirements)

    save_requirement_language_report(
        issues,
        weak_language_file,
        source_file=requirements_file,
    )

    print_requirement_language_summary(issues)
    return weak_language_file


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check requirement wording.")
    parser.add_argument("requirements_file", help="Requirements JSON to inspect.")
    args = parser.parse_args()
    run_weak_language_checker(args.requirements_file)
