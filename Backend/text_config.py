"""Parser for the repository's line-oriented term and regex configuration files."""

from pathlib import Path


def load_grouped_text_config(
    file_path: str | Path,
    *,
    regex_group: str = "regex_patterns",
) -> tuple[dict[str, set[str]], dict[str, str]]:
    """Load ``[group]`` sections and optional ``name=pattern`` regex entries.

    Duplicate section headings are rejected. Previously, duplicate headings in
    ``coverage_terms.txt`` silently replaced earlier values, which made configuration
    changes difficult to reason about.
    """

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Text configuration file not found: {path}")

    groups: dict[str, set[str]] = {}
    regex_patterns: dict[str, str] = {}
    current_group: str | None = None

    with path.open("r", encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("[") and line.endswith("]"):
                group_name = line[1:-1].strip()
                if group_name in groups:
                    raise ValueError(
                        f"Duplicate section [{group_name}] in {path} at line {line_number}."
                    )
                groups[group_name] = set()
                current_group = group_name
                continue

            if current_group is None:
                raise ValueError(
                    f"Value before a section heading in {path} at line {line_number}: {line}"
                )

            if current_group == regex_group:
                name, separator, pattern = line.partition("=")
                if not separator or not name.strip() or not pattern.strip():
                    raise ValueError(
                        f"Invalid regex entry in {path} at line {line_number}: {line}"
                    )
                if name.strip() in regex_patterns:
                    raise ValueError(
                        f"Duplicate regex name '{name.strip()}' in {path}."
                    )
                regex_patterns[name.strip()] = pattern.strip()
            else:
                groups[current_group].add(line.casefold())

    return groups, regex_patterns


def require_groups(
    groups: dict[str, set[str]],
    required_names: set[str],
    *,
    source: str | Path,
) -> None:
    """Fail during startup when a required configuration section is missing."""

    missing = required_names - groups.keys()
    if missing:
        raise ValueError(f"Missing sections in {source}: {', '.join(sorted(missing))}")
