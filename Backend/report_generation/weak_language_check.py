from datetime import datetime
import json
from pathlib import Path
import argparse

from Backend.config import WEAK_LANGUAGE_DIR

STRONG_REQUIREMENT_WORDS = [
    "must",
    "shall",
    "required",
    "requires",
    "require",
]

WEAK_REQUIREMENT_WORDS = [
    # Permission / possibility
    "may",
    "might",
    "can",
    "could",
    "is permitted to",
    "are permitted to",
    "permitted",
    "allowed",
    "allowable",
    "may be",
    "can be",
    "could be",
    "might be",

    # Optional / conditional support
    "optional",
    "optionally",
    "if supported",
    "when supported",
    "where supported",
    "if implemented",
    "when implemented",
    "where implemented",
    "implementation defined",
    "implementation-defined",
    "implementation specific",
    "implementation-specific",
    "platform dependent",
    "platform-dependent",
    "device dependent",
    "device-dependent",
    "configuration dependent",
    "configuration-dependent",
    "configurable",
    "programmable",

    # Conditional / contextual
    "where applicable",
    "if applicable",
    "when applicable",
    "as applicable",
    "as appropriate",
    "where appropriate",
    "if appropriate",
    "when appropriate",
    "as needed",
    "if needed",
    "when needed",
    "where needed",
    "as required",
    "where required",
    "if required",
    "when required",

    # Recommendations / non-mandatory guidance
    "should",
    "recommended",
    "recommend",
    "recommendation",
    "preferably",
    "preferred",
    "it is recommended",
    "it is preferable",
    "best effort",
    "best-effort",

    # Frequency / vague normality
    "typically",
    "normally",
    "generally",
    "usually",
    "commonly",
    "often",
    "in general",
    "by default",
    "default",

    # Ambiguous timing
    "timely",
    "timely manner",
    "reasonable time",
    "as soon as possible",
    "eventually",
    "soon",
    "later",
    "early",
    "earliest",
    "latest",
    "where possible",
    "if possible",
    "when possible",
    "as possible",

    # Ambiguous quantity / degree
    "approximately",
    "about",
    "around",
    "roughly",
    "near",
    "minimum necessary",
    "sufficient",
    "sufficiently",
    "adequate",
    "adequately",
    "appropriate",
    "reasonable",
    "minimal",
    "maximum possible",
    "up to",
    "at least where possible",

    # Ambiguous completeness / examples
    "including but not limited to",
    "for example",
    "such as",
    "etc",
    "and so on",
    "among others",

    # Vague behaviour
    "support",
    "supports",
    "is supported",
    "is included",
    "provided",
    "available",
    "capable of",
    "intended to",
    "designed to",
    "aims to",
    "allows",
    "enables",

    # Exceptions / unclear scope
    "unless otherwise specified",
    "where not otherwise specified",
    "except where",
    "except when",
    "subject to",
    "depending on",
    "depends on",
    "based on",
]

def unwrap_requirements(data) -> list[dict]:
    """Accept either a raw requirements list or a dict with a requirements key."""

    if isinstance(data, dict):
        data = data.get("requirements", [])

    if not isinstance(data, list):
        raise ValueError(
            "Expected requirements to be a list, or a dict containing a 'requirements' list."
        )

    return data

def get_requirement_text(requirement: dict) -> str:
    """Combine requirement fields into one searchable text string."""

    return " ".join(
        [
            str(requirement.get("description", "")),
            str(requirement.get("text", "")),
        ]
    ).lower()


def contains_word_or_phrase(text: str, words_or_phrases: list[str]) -> bool:
    """Return True if text contains any listed word or phrase."""

    return any(word_or_phrase in text for word_or_phrase in words_or_phrases)


def check_requirement_language(requirements) -> list[dict]:
    """Check requirements for weak or unclear requirement language."""

    requirements = unwrap_requirements(requirements)

    issues = []

    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue

        requirement_id = requirement.get("id", "UNKNOWN")
        text = get_requirement_text(requirement)

        has_strong_language = contains_word_or_phrase(
            text,
            STRONG_REQUIREMENT_WORDS,
        )

        has_weak_language = contains_word_or_phrase(
            text,
            WEAK_REQUIREMENT_WORDS,
        )

        if has_weak_language:
            matched_words = [
                word
                for word in WEAK_REQUIREMENT_WORDS
                if word in text
            ]

            issues.append(
                {
                    "requirement_id": requirement_id,
                    "issue_type": "weak_or_optional_language",
                    "matched_words": matched_words,
                    "message": (
                        "Requirement contains weak or optional wording. "
                        "Do not infer mandatory behaviour unless it is explicitly stated."
                    ),
                }
            )

        if not has_strong_language:
            issues.append(
                {
                    "requirement_id": requirement_id,
                    "issue_type": "missing_strong_requirement_language",
                    "message": (
                        "Requirement does not contain strong requirement wording "
                        "such as must, shall, should, required, or requires."
                    ),
                }
            )

    return issues


def save_requirement_language_report(
    issues: list[dict],
    output_file: str | Path,
) -> None:
    """Save requirement language issues to a JSON file."""

    output_path = Path(output_file)

    report = {
        "number_of_language_issues": len(issues),
        "issues": issues,
    }

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print(f"Requirement language report saved to {output_path}")


def print_requirement_language_summary(issues: list[dict]) -> None:
    """Print a readable summary of requirement language issues."""

    print("\nRequirement language check")
    print("--------------------------")
    print(f"Language issues found: {len(issues)}")

    if not issues:
        print("No weak or unclear requirement language found.")
        return

    for issue in issues:
        requirement_id = issue["requirement_id"]
        issue_type = issue["issue_type"]

        if issue_type == "weak_or_optional_language":
            matched_words = ", ".join(issue.get("matched_words", []))
            print(f"- {requirement_id}: weak language found ({matched_words})")
        else:
            print(f"- {requirement_id}: missing strong requirement language")

def get_flagged_requirements(
    requirements,
    language_issues: list[dict],
) -> list[dict]:
    """Return only requirements that have language issues."""

    requirements = unwrap_requirements(requirements)

    flagged_ids = {
        issue["requirement_id"]
        for issue in language_issues
    }

    return [
        requirement
        for requirement in requirements
        if requirement.get("id") in flagged_ids
    ]

def run_weak_language_checker(requirements_file: str) -> Path:
    print(f"Using requirements file: {requirements_file}")

    with open(requirements_file, "r", encoding="utf-8") as file:
        input_data = json.load(file)

    input_requirements = unwrap_requirements(input_data)

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    weak_language_file = WEAK_LANGUAGE_DIR / f"weak_words_{timestamp}.json"

    issues = check_requirement_language(input_requirements)
    save_requirement_language_report(issues, weak_language_file)
    print_requirement_language_summary(issues)

    return weak_language_file


REQUIREMENTS_FILE = "../ambiguous-requirements.json"

if __name__ == "__main__":
    run_weak_language_checker(REQUIREMENTS_FILE)
