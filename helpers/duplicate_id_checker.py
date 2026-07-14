import json
from collections import Counter
from pathlib import Path


def find_duplicate_requirement_ids(json_file: str | Path) -> dict[str, int]:
    file_path = Path(json_file)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    found_ids: list[str] = []

    def collect_ids(value) -> None:
        if isinstance(value, dict):
            requirement_id = value.get("id")

            if isinstance(requirement_id, str) and requirement_id.startswith("REQ_"):
                found_ids.append(requirement_id)

            for nested_value in value.values():
                collect_ids(nested_value)

        elif isinstance(value, list):
            for item in value:
                collect_ids(item)

    collect_ids(data)

    counts = Counter(found_ids)

    return {
        requirement_id: count for requirement_id, count in counts.items() if count > 1
    }


def write_duplicate_report(
    duplicates: dict[str, int],
    output_file: str | Path,
) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        if duplicates:
            file.write("Duplicate requirement IDs found:\n\n")

            for requirement_id, count in sorted(duplicates.items()):
                file.write(f"{requirement_id}: {count} occurrences\n")
        else:
            file.write("No duplicate requirement IDs found.\n")


if __name__ == "__main__":
    # Replace this with the path to your JSON file.
    JSON_FILE = "../amba-axi-extracted-7-7-26.json"
    OUTPUT_FILE = "duplicate_requirement_ids.txt"

    try:
        duplicates = find_duplicate_requirement_ids(JSON_FILE)
        write_duplicate_report(duplicates, OUTPUT_FILE)

    except (FileNotFoundError, json.JSONDecodeError) as error:
        Path(OUTPUT_FILE).write_text(
            f"Error: {error}\n",
            encoding="utf-8",
        )
