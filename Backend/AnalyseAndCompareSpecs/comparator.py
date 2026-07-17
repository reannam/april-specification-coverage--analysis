"""
Engineering specification version comparator.

This script is designed to compare two JSON files created by:
Extractor(JSON UPDATED).py

It reports minimal, specific differences between versions and writes:
  - version_differences.csv
  - version_differences.json
  - version_differences.md

  Structure of Output:
 figures
 images
 pages
 tables
    document2.json
    document_name 
    metadata 
    total_pages 
    sections 
    requirements 
    pages 
    -raw page text
    -headings found on that page
    -requirements extracted from that page
    -figures, tables, images 
    notes, figures, tables, acronyms 






Example:
python3 SpecificationVersionComparator.py \
    old_output/document.json \
    new_output/document.json


python3 Spec_Version_Comparer.py /home/eng-6990/PROJECT/extractor/RISC-V_VER.1.json /home/eng-6990/PROJECT/extractor/RISC-V_VER.2.json


FILE_PATH = r"/home/eng-6990/PROJECT/RISC-V_VER.2"



RVB23 Profile Oct. 2024
RISC-V Profiles April 2023

"""

import argparse
import csv
import difflib
import hashlib
import json
import os
import re
import unicodedata
from functools import lru_cache
from datetime import datetime

from Backend.config import SPEC_COMPARISON_DIR

# ==========================================================
# CONFIGURATION
# ==========================================================

OUTPUT_DIR = SPEC_COMPARISON_DIR

DEFAULT_CSV_NAME = "version_differences.csv"
DEFAULT_JSON_NAME = "version_differences.json"
DEFAULT_MD_NAME = "version_differences.md"

NUMBER_REGEX = re.compile(
    r"[-+]?\d+(?:\.\d+)?(?:\s*(?:%|v|a|hz|khz|mhz|ghz|ms|us|ns|s|kb|mb|gb|bit|bits|byte|bytes))?",
    re.IGNORECASE,
)

REFERENCE_REGEX = re.compile(
    r"\b(?:section|figure|fig\.?|table)\s+[A-Za-z]?\d+(?:[-.]\d+)*",
    re.IGNORECASE,
)

REQUIREMENT_WORD_REGEX = re.compile(
    r"\b(shall|must|will|should|required to|may not|is prohibited|may|can)\b",
    re.IGNORECASE,
)

TOKEN_REGEX = re.compile(r"[a-z0-9_]+", re.IGNORECASE)

COMMON_TOKENS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "shall",
    "must",
    "should",
    "will",
    "may",
    "can",
    "are",
    "was",
    "were",
    "has",
    "have",
    "not",
    "when",
    "then",
    "than",
    "into",
    "only",
    "value",
    "values",
    "section",
    "figure",
    "table",
}

MAX_SIMILAR_CANDIDATES_PER_ITEM = 20

SOFT_HYPHEN = "\u00ad"

# Technical identifiers that must survive normalisation untouched:
# hex literals (0x1000), ISA strings (RV64GC, RV32IMAFDC), dotted
# instruction mnemonics (FENCE.I, AMOCAS.D), and common CSR names
# (mstatus, satp, pmpcfg0, ...). This list is a heuristic, not
# exhaustive -- extend it if normalisation is ever seen mangling a
# token it shouldn't.
TECHNICAL_TOKEN_REGEX = re.compile(
    r"\b("
    r"0[xX][0-9A-Fa-f]+"
    r"|RV(?:32|64|128)[A-Za-z0-9_]*"
    r"|[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z0-9]+)+"
    r"|[a-z][a-z0-9]{2,}(?:status|cause|tval|tvec|epc|scratch|ie|ip|atp|cfg\d*|addr\d*)"
    r")\b"
)


# ==========================================================
# FILE HELPERS
# ==========================================================


def resolve_document_json(path):

    if os.path.isdir(path):
        candidate = os.path.join(path, "document.json")

        if os.path.exists(candidate):
            return candidate

    return path


def load_json(path):
    # Normalise Path inputs at the boundary so report metadata remains JSON-safe.
    resolved_path = os.fspath(resolve_document_json(path))

    with open(resolved_path, "r", encoding="utf-8") as f:
        document = json.load(f)

    if isinstance(document, dict):
        document["_source_path"] = resolved_path
        document["_source_dir"] = os.path.dirname(resolved_path)

    return document, resolved_path


def ensure_output_dir(path):

    os.makedirs(path, exist_ok=True)


# ==========================================================
# NORMALISATION
# ==========================================================


def clean_text(value):

    if value is None:
        return ""

    text = str(value)

    # Remove spaces around hyphens
    text = re.sub(r"\s*-\s*", "-", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalise_comparison_text(value):

    text = clean_text(value).lower()

    # Remove common extraction artefacts
    text = re.sub(r"\s+", " ", text)

    # Fix hyphenation
    text = re.sub(r"\s*-\s*", "-", text)

    return text.strip()


def normalize_paragraph(text, protect_technical_tokens=True):
    """
    Canonical form used for hashing and similarity comparison.
    Removes PDF extraction artefacts (soft hyphens, hyphenated line
    wraps, hard line wraps, stray whitespace/punctuation spacing)
    while preserving technical meaning. Not for display -- callers
    that need reviewer-facing text should keep using clean_text().
    """

    if not text:
        return ""

    text = str(text)

    protected_tokens = {}

    if protect_technical_tokens:

        def _protect(match):
            token = match.group(0)
            placeholder = f"\u0000TOK{len(protected_tokens)}\u0000"
            protected_tokens[placeholder] = token
            return placeholder

        text = TECHNICAL_TOKEN_REGEX.sub(_protect, text)

    # Unicode canonicalisation
    text = unicodedata.normalize("NFKC", text)
    # Remove soft hyphens
    text = text.replace(SOFT_HYPHEN, "")
    # Join hyphenated line breaks: memory-\nmanagement -> memory-management
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1-\2", text)
    # Join wrapped lines inside paragraphs
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Normalise punctuation spacing
    text = re.sub(r"\s+([,.;:])", r"\1", text)

    text = text.strip()

    for placeholder, token in protected_tokens.items():
        text = text.replace(placeholder, token)

    return text


def stable_hash(value):

    normalised = clean_text(value).lower()

    return hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:12]


def similarity(old_value, new_value):

    return round(
        difflib.SequenceMatcher(
            None,
            normalise_comparison_text(old_value),
            normalise_comparison_text(new_value),
        ).ratio(),
        4,
    )


def first_changed_phrase(old_value, new_value):

    old_words = normalise_comparison_text(old_value).split()
    new_words = normalise_comparison_text(new_value).split()

    matcher = difflib.SequenceMatcher(None, old_words, new_words)

    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():

        if tag == "equal":
            continue

        old_phrase = " ".join(old_words[old_start:old_end])

        new_phrase = " ".join(new_words[new_start:new_end])

        return old_phrase, new_phrase

    return "", ""


def extract_numbers(text):

    return [
        clean_text(match.group(0)).lower()
        for match in NUMBER_REGEX.finditer(clean_text(text))
    ]


def extract_requirement_words(text):

    return [
        match.group(1).lower()
        for match in REQUIREMENT_WORD_REGEX.finditer(clean_text(text))
    ]


def extract_references(text):

    return [
        clean_text(match.group(0)).lower()
        for match in REFERENCE_REGEX.finditer(clean_text(text))
    ]


def normalised_content(value):

    return clean_text(value).lower()


def page_number(item):

    page = item.get("page")

    if page is None:
        page = item.get("page_number")

    if page is None:
        page = item.get("source_page")

    try:
        return int(page)
    except (TypeError, ValueError):
        return None


def page_range(values):

    numbers = sorted(value for value in values if isinstance(value, int))

    if not numbers:
        return ""

    start = numbers[0]
    end = numbers[-1]

    if start == end:
        return str(start)

    return f"{start}–{end}"


def resolve_content_path(path_value, document):
    path_value = clean_text(path_value)
    source_dir = clean_text(document.get("_source_dir"))

    if not path_value or not source_dir:
        return ""

    source_root = os.path.realpath(source_dir)
    candidate = os.path.realpath(
        path_value
        if os.path.isabs(path_value)
        else os.path.join(source_root, path_value)
    )

    # Extractor JSON is an input document, not authority to read arbitrary host
    # paths. Referenced table content must remain beside or beneath that JSON.
    if os.path.commonpath([source_root, candidate]) != source_root:
        return ""

    if os.path.isfile(candidate):
        return candidate

    return ""


@lru_cache(maxsize=4096)
def read_csv_rows(path):

    if not path:
        return []

    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            return [
                [clean_text(cell) for cell in row]
                for row in csv.reader(f)
                if any(clean_text(cell) for cell in row)
            ]
    except OSError:
        return []


def significant_tokens(value):

    tokens = []
    seen = set()

    for token in TOKEN_REGEX.findall(normalised_content(value)):
        if len(token) < 3 or token in COMMON_TOKENS or token in seen:
            continue

        seen.add(token)
        tokens.append(token)

    return tokens


def table_rows(table, document):

    return read_csv_rows(resolve_content_path(table.get("csv_file"), document))


def rows_to_text(rows):

    return "\n".join(" | ".join(cell for cell in row) for row in rows)


def table_content(table, document):

    rows = table_rows(table, document)

    if rows:
        return rows_to_text(rows)

    fallback_parts = [
        table.get("caption"),
        table.get("title"),
        table.get("text"),
        table.get("ocr_text"),
        table.get("accessibility_description"),
    ]

    return " ".join(clean_text(part) for part in fallback_parts if clean_text(part))


def table_preview(table, document):

    rows = table_rows(table, document)

    if not rows:
        return clean_text(table.get("caption")) or "Table"

    for row in rows:
        populated = [cell for cell in row if cell]
        if populated:
            return " | ".join(populated[:4])

    return "Table"


def figure_content(figure, document):

    del document

    return figure.get("caption")


def figure_preview(figure, document):

    del document

    return clean_text(figure.get("caption")) or "Figure"


def text_content(field_name):

    def content(item, document):
        del document
        return item.get(field_name)

    return content


def text_preview(field_name, label):

    def preview(item, document):
        del document
        value = clean_text(item.get(field_name))
        if not value:
            return label
        if len(value) <= 120:
            return value
        return f"{value[:117]}..."

    return preview


def describe_table_difference(old_item, new_item, old_document, new_document):

    old_rows = table_rows(old_item, old_document)
    new_rows = table_rows(new_item, new_document)

    if not old_rows or not new_rows:
        return None, None, None, None

    max_rows = max(len(old_rows), len(new_rows))
    changed_cells = []

    for row_index in range(max_rows):
        old_row = old_rows[row_index] if row_index < len(old_rows) else None
        new_row = new_rows[row_index] if row_index < len(new_rows) else None

        if old_row is None and new_row is not None:
            context = f"Row {row_index + 1}: " + " | ".join(new_row)
            return "Row added", "", " | ".join(new_row), context

        if new_row is None and old_row is not None:
            context = f"Row {row_index + 1}: " + " | ".join(old_row)
            return "Row removed", " | ".join(old_row), "", context

        max_columns = max(len(old_row), len(new_row))

        for column_index in range(max_columns):
            old_cell = old_row[column_index] if column_index < len(old_row) else ""
            new_cell = new_row[column_index] if column_index < len(new_row) else ""

            if clean_text(old_cell) != clean_text(new_cell):
                changed_cells.append((row_index, column_index, old_cell, new_cell))

    if not changed_cells:
        return None, None, None, None

    first_row_index = changed_cells[0][0]
    context_row = (
        new_rows[first_row_index]
        if first_row_index < len(new_rows)
        else old_rows[first_row_index]
    )
    context = f"Row {first_row_index + 1}: " + " | ".join(context_row)

    if len(changed_cells) == 1:
        row_index, column_index, old_cell, new_cell = changed_cells[0]
        detail = f"Cell changed (row {row_index + 1}, col {column_index + 1})"
        return detail, old_cell, new_cell, context

    old_summary = "\n".join(
        f"[row {r + 1}, col {c + 1}] {old_cell}"
        for r, c, old_cell, new_cell in changed_cells
    )
    new_summary = "\n".join(
        f"[row {r + 1}, col {c + 1}] {new_cell}"
        for r, c, old_cell, new_cell in changed_cells
    )
    detail = f"{len(changed_cells)} cells changed"
    return detail, old_summary, new_summary, context


# ==========================================================
# DIFFERENCE CLASSIFICATION
# ==========================================================


def classify_modified_text(old_value, new_value):

    old_numbers = extract_numbers(old_value)
    new_numbers = extract_numbers(new_value)

    if old_numbers != new_numbers:
        return "numeric_value_change"

    old_requirement_words = extract_requirement_words(old_value)
    new_requirement_words = extract_requirement_words(new_value)

    if old_requirement_words != new_requirement_words:
        return "requirement_strength_change"

    old_references = extract_references(old_value)
    new_references = extract_references(new_value)

    if old_references != new_references:
        return "cross_reference_change"

    old_text = clean_text(old_value).lower()
    new_text = clean_text(new_value).lower()

    if not old_text or not new_text:
        return "content_change"

    score = similarity(old_text, new_text)

    if score is None:
        return "content_change"

    if score >= 0.90:
        return "minor_wording_change"

    if score >= 0.65:
        return "substantive_wording_change"

    return "content_change"


def make_change(
    change_id,
    area,
    change_type,
    difference_category,
    identifier,
    old_value,
    new_value,
    section=None,
    page=None,
    detail=None,
    old_page=None,
    new_page=None,
    preview=None,
    display_title=None,
    **extra,
):

    if detail is None:
        old_phrase, new_phrase = first_changed_phrase(old_value, new_value)

        if old_phrase or new_phrase:
            detail = f"Changed '{old_phrase}' to '{new_phrase}'"
        else:
            detail = change_type.replace("_", " ")

    change = {
        "change_id": change_id,
        "area": area,
        "change_type": change_type,
        "difference_category": difference_category,
        "identifier": identifier,
        "section": section,
        "page": page,
        "old_page": old_page,
        "new_page": new_page,
        "preview": preview,
        "display_title": display_title,
        "old_value": clean_text(old_value),
        "new_value": clean_text(new_value),
        "detail": detail,
        "similarity": similarity(old_value, new_value),
    }

    change.update(extra)

    return change


# ==========================================================
# INDEXING
# ==========================================================


def indexed_items(items, key_function):

    indexed = {}

    for index, item in enumerate(items or [], start=1):

        key = key_function(item, index)

        if key in indexed:
            key = f"{key}:{index}"

        indexed[key] = item

    return indexed


def section_key(section, fallback_index):

    section_id = clean_text(section.get("id"))

    if section_id:
        return section_id

    return f"title:{stable_hash(section.get('title'))}:{fallback_index}"


def requirement_key(item, index):

    for field in [
        "requirement_id",
        "id",
        "identifier",
        "name",
        "req_id",
        "requirement",
    ]:
        value = clean_text(item.get(field))
        if value:
            return f"REQ:{value}"

    return f"REQ:{index}"


def page_key(page, fallback_index):

    number = page.get("page_number")

    if number is not None:
        return str(number)

    return str(fallback_index)


def metadata_items(metadata):

    metadata_keys = {
        "title",
        "version",
        "revision",
    }

    return {
        key: clean_text(value)
        for key, value in (metadata or {}).items()
        if key.lower() in metadata_keys
    }


# ==========================================================
# COMPARISON
# ==========================================================


def item_record(
    item, index, document, content_function, preview_function, key_function=None
):

    raw_value = content_function(item, document)

    content = clean_text(raw_value)
    normalized_text = normalize_paragraph(raw_value)
    tokens = significant_tokens(normalized_text)

    return {
        "item": item,
        "index": index,
        "key": (key_function(item, index) if key_function else index),
        "content": content,
        "normalized_text": normalized_text,
        "normalised": normalised_content(content),
        "hash": stable_hash(normalized_text),
        "tokens": tokens,
        "token_set": set(tokens),
        "length": len(content),
        "page": page_number(item),
        "section": item.get("section"),
        "preview": preview_function(item, document),
    }


def match_exact_content(old_records, new_records):

    old_by_hash = {}
    new_by_hash = {}

    for record in old_records:
        if record["normalised"]:
            old_by_hash.setdefault(record["hash"], []).append(record)

    for record in new_records:
        if record["normalised"]:
            new_by_hash.setdefault(record["hash"], []).append(record)

    matches = []
    matched_old = set()
    matched_new = set()

    for content_hash in sorted(set(old_by_hash) & set(new_by_hash)):
        old_bucket = old_by_hash[content_hash]
        new_bucket = new_by_hash[content_hash]

        for old_record, new_record in zip(old_bucket, new_bucket):
            matches.append((old_record, new_record))
            matched_old.add(old_record["index"])
            matched_new.add(new_record["index"])

    return matches, matched_old, matched_new


def match_similar_content(
    old_records, new_records, matched_old, matched_new, minimum_score
):

    token_index = {}
    unmatched_new = []
    new_by_index = {}

    for new_record in new_records:
        if new_record["index"] in matched_new or not new_record["normalised"]:
            continue

        unmatched_new.append(new_record)
        new_by_index[new_record["index"]] = new_record

        for token in new_record["tokens"][:40]:
            token_index.setdefault(token, []).append(new_record)

    candidates = []

    for old_record in old_records:
        if old_record["index"] in matched_old or not old_record["normalised"]:
            continue

        candidate_scores = {}

        for token in old_record["tokens"][:40]:
            for new_record in token_index.get(token, []):
                if new_record["index"] in matched_new:
                    continue

                candidate_scores[new_record["index"]] = (
                    candidate_scores.get(new_record["index"], 0) + 1
                )

        if not candidate_scores:
            continue

        ranked_new_records = sorted(
            (
                (token_score, new_by_index[new_index])
                for new_index, token_score in candidate_scores.items()
                if new_index in new_by_index
            ),
            key=lambda candidate: candidate[0],
            reverse=True,
        )[:MAX_SIMILAR_CANDIDATES_PER_ITEM]

        for token_score, new_record in ranked_new_records:
            old_length = old_record["length"] or 1
            new_length = new_record["length"] or 1
            length_ratio = min(old_length, new_length) / max(old_length, new_length)

            if length_ratio < 0.35:
                continue

            token_union = old_record["token_set"] | new_record["token_set"]
            token_overlap = token_score / len(token_union) if token_union else 0

            if token_overlap < 0.08:
                continue

            score = similarity(
                old_record["normalized_text"], new_record["normalized_text"]
            )

            if score >= minimum_score:
                candidates.append((score, old_record, new_record))

    candidates.sort(key=lambda candidate: candidate[0], reverse=True)

    matches = []

    for score, old_record, new_record in candidates:
        if old_record["index"] in matched_old or new_record["index"] in matched_new:
            continue

        matches.append((old_record, new_record, score))
        matched_old.add(old_record["index"])
        matched_new.add(new_record["index"])

    return matches


def compare_content_area(
    old_document,
    new_document,
    area,
    text_field,
    old_items,
    new_items,
    changes,
    content_function,
    preview_function,
    relocation_enabled=True,
    modification_threshold=0.72,
    key_function=None,
):
    old_records = [
        item_record(
            item, index, old_document, content_function, preview_function, key_function
        )
        for index, item in enumerate(old_items or [], start=1)
    ]

    new_records = [
        item_record(
            item, index, new_document, content_function, preview_function, key_function
        )
        for index, item in enumerate(new_items or [], start=1)
    ]

    # ======================================================
    # MATCH BY KEY (requirements use requirement_key)
    # ======================================================

    matched_old = set()
    matched_new = set()

    if key_function:

        old_by_key = {record["key"]: record for record in old_records}

        new_by_key = {record["key"]: record for record in new_records}

        for key in sorted(set(old_by_key.keys()) & set(new_by_key.keys())):

            old_record = old_by_key[key]
            new_record = new_by_key[key]

            if old_record["normalized_text"] != new_record["normalized_text"]:

                changes.append(
                    make_change(
                        f"CHG-{len(changes)+1:04}",
                        area,
                        "modified",
                        classify_modified_text(
                            old_record["normalized_text"], new_record["normalized_text"]
                        ),
                        key,
                        old_record["content"],
                        new_record["content"],
                        section=new_record["section"],
                        page=new_record["page"],
                        old_page=old_record["page"],
                        new_page=new_record["page"],
                        preview=new_record["preview"],
                        display_title=f"{area.title()} modified",
                    )
                )

            matched_old.add(old_record["index"])
            matched_new.add(new_record["index"])

    exact_matches, exact_old, exact_new = match_exact_content(
        [r for r in old_records if r["index"] not in matched_old],
        [r for r in new_records if r["index"] not in matched_new],
    )

    matched_old.update(exact_old)
    matched_new.update(exact_new)

    for old_record, new_record in exact_matches:
        moved = old_record["page"] != new_record["page"] or clean_text(
            old_record["section"]
        ) != clean_text(new_record["section"])

        if relocation_enabled and moved:
            changes.append(
                make_change(
                    f"CHG-{len(changes)+1:04}",
                    area,
                    "moved",
                    f"{area}_moved",
                    old_record["preview"],
                    "",
                    "",
                    section=new_record["section"] or old_record["section"],
                    page=new_record["page"],
                    old_page=old_record["page"],
                    new_page=new_record["page"],
                    preview=old_record["preview"],
                    display_title=f"{area.title()} moved",
                    detail="Content unchanged",
                )
            )

    similar_matches = match_similar_content(
        old_records, new_records, matched_old, matched_new, modification_threshold
    )

    for old_record, new_record, score in similar_matches:
        old_value = old_record["content"]
        new_value = new_record["content"]
        detail = None
        table_context = None

        if area == "table":
            detail, table_old_value, table_new_value, table_context = (
                describe_table_difference(
                    old_record["item"], new_record["item"], old_document, new_document
                )
            )

            if detail:
                old_value = table_old_value
                new_value = table_new_value

        change_preview = table_context or new_record["preview"] or old_record["preview"]

        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                area,
                "modified",
                classify_modified_text(
                    old_record["normalized_text"], new_record["normalized_text"]
                ),
                change_preview,
                old_value,
                new_value,
                section=new_record["section"] or old_record["section"],
                page=new_record["page"] or old_record["page"],
                old_page=old_record["page"],
                new_page=new_record["page"],
                preview=change_preview,
                display_title=f"{area.title()} modified",
                detail=detail,
                similarity_score=score,
            )
        )

    for record in old_records:
        if record["index"] in matched_old:
            continue

        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                area,
                "removed",
                f"{area}_removed",
                record["preview"],
                record["content"],
                "",
                section=record["section"],
                page=record["page"],
                old_page=record["page"],
                preview=record["preview"],
                display_title=f"{area.title()} removed",
                detail=f"Removed {area}",
            )
        )

    for record in new_records:
        if record["index"] in matched_new:
            continue

        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                area,
                "added",
                f"{area}_added",
                record["preview"],
                "",
                record["content"],
                section=record["section"],
                page=record["page"],
                new_page=record["page"],
                preview=record["preview"],
                display_title=f"{area.title()} added",
                detail=f"Added {area}",
            )
        )


def compare_sections(old_document, new_document, changes):

    old_sections = indexed_items(old_document.get("sections"), section_key)

    new_sections = indexed_items(new_document.get("sections"), section_key)

    all_keys = sorted(set(old_sections.keys()) | set(new_sections.keys()))

    for key in all_keys:

        old_section = old_sections.get(key)
        new_section = new_sections.get(key)
        change_id = f"CHG-{len(changes)+1:04}"

        if old_section is None:
            changes.append(
                make_change(
                    change_id,
                    "section",
                    "added",
                    "section_added",
                    key,
                    "",
                    new_section.get("title"),
                    section=key,
                    detail="Added section",
                )
            )
            continue

        if new_section is None:
            changes.append(
                make_change(
                    change_id,
                    "section",
                    "removed",
                    "section_removed",
                    key,
                    old_section.get("title"),
                    "",
                    section=key,
                    detail="Removed section",
                )
            )
            continue

        if clean_text(old_section.get("title")) != clean_text(new_section.get("title")):
            changes.append(
                make_change(
                    change_id,
                    "section",
                    "modified",
                    classify_modified_text(
                        old_section.get("title"), new_section.get("title")
                    ),
                    key,
                    old_section.get("title"),
                    new_section.get("title"),
                    section=key,
                )
            )


def compare_metadata(old_document, new_document, changes):

    old_metadata = metadata_items(old_document.get("metadata"))

    new_metadata = metadata_items(new_document.get("metadata"))

    all_keys = sorted(set(old_metadata.keys()) | set(new_metadata.keys()))

    for key in all_keys:

        old_value = old_metadata.get(key, "")
        new_value = new_metadata.get(key, "")

        if old_value == new_value:
            continue

        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                "metadata",
                "modified",
                "metadata_change",
                key,
                old_value,
                new_value,
                detail=f"Metadata field changed: {key}",
            )
        )


def compare_acronyms(old_document, new_document, changes):

    old_acronyms = set(clean_text(value) for value in old_document.get("acronyms", []))

    new_acronyms = set(clean_text(value) for value in new_document.get("acronyms", []))

    for acronym in sorted(new_acronyms - old_acronyms):
        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                "acronym",
                "added",
                "acronym_added",
                acronym,
                "",
                acronym,
                detail="Added acronym",
            )
        )

    for acronym in sorted(old_acronyms - new_acronyms):
        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                "acronym",
                "removed",
                "acronym_removed",
                acronym,
                acronym,
                "",
                detail="Removed acronym",
            )
        )


def compare_page_text(old_document, new_document, changes):

    old_records = []

    for index, page in enumerate(old_document.get("pages") or [], start=1):

        record = item_record(
            page,
            index,
            old_document,
            text_content("text"),
            text_preview("text", "Page"),
        )

        old_records.append(record)

    new_records = []

    for index, page in enumerate(new_document.get("pages") or [], start=1):

        record = item_record(
            page,
            index,
            new_document,
            text_content("text"),
            text_preview("text", "Page"),
        )

        new_records.append(record)

    # ----------------------------------------------------------
    # MATCH PAGE CONTENT
    # ----------------------------------------------------------

    exact_matches, matched_old, matched_new = match_exact_content(
        old_records, new_records
    )

    similar_matches = match_similar_content(
        old_records, new_records, matched_old, matched_new, 0.30
    )

    page_matches = [
        (old_record, new_record) for old_record, new_record in exact_matches
    ]

    page_matches.extend(
        (old_record, new_record) for old_record, new_record, score in similar_matches
    )

    # ----------------------------------------------------------
    # Detect structural page shift
    # ----------------------------------------------------------

    offsets = {}
    offset_pages = {}

    for old_record, new_record in page_matches:

        old_page = old_record["page"]
        new_page = new_record["page"]

        if not isinstance(old_page, int) or not isinstance(new_page, int):
            continue

        offset = new_page - old_page

        if offset == 0:
            continue

        offsets[offset] = offsets.get(offset, 0) + 1
        offset_pages.setdefault(offset, []).append(old_page)

    dominant_offset = 0

    if offsets:

        candidate_offset, count = max(offsets.items(), key=lambda item: item[1])

        if count >= 3:

            dominant_offset = candidate_offset

            changes.append(
                make_change(
                    f"CHG-{len(changes)+1:04}",
                    "page",
                    "moved",
                    "structural_page_shift",
                    "Structural page shift",
                    "",
                    "",
                    detail=(
                        "Structural page shift detected. "
                        f"Pages {page_range(offset_pages[candidate_offset])} "
                        f"were renumbered by {candidate_offset:+}. "
                        "Content was matched successfully."
                    ),
                    old_page=page_range(offset_pages[candidate_offset]),
                    new_page=page_range(
                        [p + candidate_offset for p in offset_pages[candidate_offset]]
                    ),
                    page_shift=candidate_offset,
                    display_title="Structural page shift detected",
                )
            )

    # ----------------------------------------------------------
    # Build lookup by page number
    # ----------------------------------------------------------

    new_by_page = {
        record["page"]: record
        for record in new_records
        if isinstance(record["page"], int)
    }
    # ----------------------------------------------------------
    # Compare corresponding pages
    # ----------------------------------------------------------

    for old_record in old_records:

        if old_record["index"] in matched_old:
            continue

        if not isinstance(old_record["page"], int):
            continue

        target_page = old_record["page"] + dominant_offset

        new_record = new_by_page.get(target_page)

        if new_record is None:
            continue

        if new_record["index"] in matched_new:
            continue

        score = similarity(old_record["normalized_text"], new_record["normalized_text"])

        if score >= 0.3:

            matched_old.add(old_record["index"])
            matched_new.add(new_record["index"])

            changes.append(
                make_change(
                    f"CHG-{len(changes)+1:04}",
                    "page",
                    "modified",
                    classify_modified_text(
                        old_record["normalized_text"], new_record["normalized_text"]
                    ),
                    f"Page {old_record['page']}",
                    old_record["content"],
                    new_record["content"],
                    page=new_record["page"],
                    old_page=old_record["page"],
                    new_page=new_record["page"],
                    display_title="Page modified",
                    similarity_score=score,
                )
            )

    # ----------------------------------------------------------
    # Removed pages
    # ----------------------------------------------------------

    for record in old_records:

        if record["index"] in matched_old:
            continue

        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                "page",
                "removed",
                "page_removed",
                f"Page {record['page']}",
                "",
                "",
                page=record["page"],
                old_page=record["page"],
                display_title="Page removed",
                detail="Removed page",
            )
        )

    # ----------------------------------------------------------
    # Added pages
    # ----------------------------------------------------------

    for record in new_records:

        if record["index"] in matched_new:
            continue

        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                "page",
                "added",
                "page_added",
                f"Page {record['page']}",
                "",
                "",
                page=record["page"],
                new_page=record["page"],
                display_title="Page added",
                detail="Added page",
            )
        )


def compare_documents(old_document, new_document):

    changes = []

    compare_metadata(old_document, new_document, changes)

    compare_sections(old_document, new_document, changes)

    compare_content_area(
        old_document,
        new_document,
        "requirement",
        "text",
        old_document.get("requirements"),
        new_document.get("requirements"),
        changes,
        text_content("text"),
        text_preview("text", "Requirement"),
        relocation_enabled=False,
        modification_threshold=0.78,
    )

    compare_content_area(
        old_document,
        new_document,
        "note",
        "text",
        old_document.get("notes"),
        new_document.get("notes"),
        changes,
        text_content("text"),
        text_preview("text", "Note"),
        relocation_enabled=True,
        modification_threshold=0.78,
    )

    compare_content_area(
        old_document,
        new_document,
        "figure",
        "caption",
        old_document.get("figures"),
        new_document.get("figures"),
        changes,
        figure_content,
        figure_preview,
        relocation_enabled=True,
        modification_threshold=0.70,
    )

    compare_content_area(
        old_document,
        new_document,
        "table",
        "csv_file",
        old_document.get("tables"),
        new_document.get("tables"),
        changes,
        table_content,
        table_preview,
        relocation_enabled=True,
        modification_threshold=0.65,
    )

    compare_page_text(old_document, new_document, changes)

    return changes


# ==========================================================
# OUTPUT
# ==========================================================

REPORT_LAYOUT = [
    (
        "Critical Changes",
        [
            ("Requirement changes", "requirement_changes"),
            ("Numeric changes", "numeric_changes"),
            ("Requirement strength changes", "requirement_strength_changes"),
        ],
    ),
    (
        "Content Changes",
        [
            ("Modified tables", "modified_tables"),
            ("Modified figures", "modified_figures"),
            ("Modified notes", "modified_notes"),
        ],
    ),
    (
        "Structural Changes",
        [
            ("Sections added", "sections_added"),
            ("Sections removed", "sections_removed"),
            ("Pages added", "pages_added"),
            ("Pages removed", "pages_removed"),
        ],
    ),
    (
        "Relocations",
        [
            ("Moved tables", "moved_tables"),
            ("Moved notes", "moved_notes"),
            ("Moved figures", "moved_figures"),
            ("Page shifts", "page_shifts"),
        ],
    ),
    (
        "Metadata",
        [
            ("Title", "metadata_title"),
            ("Version", "metadata_version"),
            ("Revision", "metadata_revision"),
        ],
    ),
]


def report_bucket(change):

    area = change.get("area")
    change_type = change.get("change_type")
    category = change.get("difference_category")
    identifier = clean_text(change.get("identifier")).lower()

    if area == "requirement" and category == "numeric_value_change":
        return "numeric_changes"

    if area == "requirement" and category == "requirement_strength_change":
        return "requirement_strength_changes"

    if area == "requirement":
        return "requirement_changes"

    if area == "table" and change_type in {"added", "removed", "modified"}:
        return "modified_tables"

    if area == "figure" and change_type in {"added", "removed", "modified"}:
        return "modified_figures"

    if area == "note" and change_type in {"added", "removed", "modified"}:
        return "modified_notes"

    if area == "section" and change_type == "added":
        return "sections_added"

    if area == "section" and change_type == "removed":
        return "sections_removed"

    if area == "page" and change_type == "added":
        return "pages_added"

    if area == "page" and change_type == "removed":
        return "pages_removed"

    if area == "table" and change_type == "moved":
        return "moved_tables"

    if area == "note" and change_type == "moved":
        return "moved_notes"

    if area == "figure" and change_type == "moved":
        return "moved_figures"

    if category == "structural_page_shift":
        return "page_shifts"

    if area == "metadata":
        if identifier == "title":
            return "metadata_title"
        if identifier == "version":
            return "metadata_version"
        if identifier == "revision":
            return "metadata_revision"

    return "requirement_changes"


def bucket_labels():

    labels = {}

    for section, buckets in REPORT_LAYOUT:
        for label, bucket in buckets:
            labels[bucket] = (section, label)

    return labels


def organise_changes(changes):

    organised = {}

    for section, buckets in REPORT_LAYOUT:
        organised[section] = {}
        for label, bucket in buckets:
            organised[section][label] = []

    for change in changes:
        bucket = report_bucket(change)
        labels = bucket_labels()
        section, label = labels.get(bucket, ("Critical Changes", "Requirement changes"))
        organised[section][label].append(change)

    return organised


# ==========================================================
# MARKDOWN REPORT HELPERS
# ==========================================================

SECTION_ICONS = {
    "Critical Changes": "🔴",
    "Content Changes": "🟠",
    "Structural Changes": "🟡",
    "Relocations": "🔵",
    "Metadata": "⚪",
}


def slugify(text):
    """GitHub-style anchor slug: lowercase, strip punctuation, spaces -> hyphens."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text


def format_similarity(value):
    if value is None:
        return None
    return f"{value * 100:.0f}%"


def md_code_block(text):
    """Wrap text in a fenced code block, escaping any accidental triple-backticks
    in the source content so the fence can't be broken out of."""
    text = text or ""
    fence = "```"
    if "```" in text:
        fence = "````"
    return f"{fence}\n{text}\n{fence}"


def change_sort_key(change):
    """Sort by page (reading order), pushing changes with no page to the end."""
    page = change.get("page")
    if not isinstance(page, int):
        page = (
            change.get("new_page") if isinstance(change.get("new_page"), int) else None
        )
    if not isinstance(page, int):
        page = (
            change.get("old_page") if isinstance(change.get("old_page"), int) else None
        )

    return (page is None, page or 0, change.get("change_id", ""))


def render_change_block(change, icon):
    """Render one change as a collapsible <details> card."""

    lines = []

    title = (
        clean_text(change.get("display_title")) or change.get("change_type", "").title()
    )
    identifier = clean_text(change.get("identifier"))
    page = change.get("page") or change.get("new_page") or change.get("old_page") or ""
    sim = format_similarity(change.get("similarity"))

    summary_bits = [icon, f"**{change['change_id']}**", title]
    if identifier:
        summary_bits.append(f"`{identifier}`")
    if page:
        summary_bits.append(f"(p. {page})")
    if sim:
        summary_bits.append(f"— {sim} similar")

    lines.append("<details>")
    lines.append(f"<summary>{' '.join(summary_bits)}</summary>")
    lines.append("")

    if change.get("old_page") or change.get("new_page"):
        old_page = change.get("old_page") or "?"
        new_page = change.get("new_page") or "?"
        lines.append(f"**Page:** {old_page} → {new_page}")
        lines.append("")

    preview = clean_text(change.get("preview"))
    if preview and preview not in (change.get("old_value"), change.get("new_value")):
        lines.append(f"**Preview:** {preview}")
        lines.append("")

    if change.get("old_value"):
        lines.append("**Old:**")
        lines.append(md_code_block(change["old_value"]))
        lines.append("")

    if change.get("new_value"):
        lines.append("**New:**")
        lines.append(md_code_block(change["new_value"]))
        lines.append("")

    if change.get("detail"):
        lines.append(f"**Detail:** {change['detail']}")
        lines.append("")

    lines.append("</details>")
    lines.append("")

    return lines


# ==========================================================
# MAIN REPORT WRITER
# ==========================================================


def write_markdown_report(
    changes, md_path, old_path, new_path, old_document, new_document
):
    summary = summarise_changes(changes)
    now = datetime.now().isoformat(timespec="seconds")
    organised = organise_changes(changes)  # preserves REPORT_LAYOUT order already

    lines = []

    # ---- Title / doc header ----
    lines.append("# Specification Version Comparison Report\n")
    lines.append(f"**Generated:** {now}  ")
    lines.append(
        f"**Old document:** `{old_path}` — "
        f"{old_document.get('document_name', 'unknown')} "
        f"({old_document.get('total_pages', '?')} pages)  "
    )
    lines.append(
        f"**New document:** `{new_path}` — "
        f"{new_document.get('document_name', 'unknown')} "
        f"({new_document.get('total_pages', '?')} pages)"
    )
    lines.append("")

    # ---- At-a-glance badge line ----
    badge_bits = []
    for section, categories in organised.items():
        count = sum(len(v) for v in categories.values())
        icon = SECTION_ICONS.get(section, "")
        badge_bits.append(f"{icon} **{count}** {section}")
    lines.append(" · ".join(badge_bits))
    lines.append("")
    lines.append(f"**Total changes:** {summary['total_changes']}")
    lines.append("")
    lines.append("---\n")

    # ---- Table of contents ----
    lines.append("## Table of Contents\n")
    lines.append("- [Summary](#summary)")
    for section, categories in organised.items():
        section_total = sum(len(v) for v in categories.values())
        if section_total == 0:
            continue
        icon = SECTION_ICONS.get(section, "")
        section_anchor = slugify(section)
        lines.append(f"- [{icon} {section}](#{section_anchor}) ({section_total})")
        for label, category_changes in categories.items():
            if not category_changes:
                continue
            sub_anchor = slugify(f"{section}-{label}")
            lines.append(f"  - [{label}](#{sub_anchor}) ({len(category_changes)})")
    lines.append("")
    lines.append("---\n")

    # ---- Summary tables (safe: counts + short labels only) ----
    lines.append("## Summary\n")
    for summary_section, label in [
        ("by_area", "By Area"),
        ("by_change_type", "By Change Type"),
        ("by_difference_category", "By Difference Category"),
    ]:
        lines.append(f"### {label}\n")
        lines.append("| Category | Count |")
        lines.append("|---|---|")
        for key, count in sorted(
            summary[summary_section].items(), key=lambda kv: -kv[1]
        ):
            lines.append(f"| {key} | {count} |")
        lines.append("")

    lines.append("---\n")

    # ---- Detail sections ----
    for section, categories in organised.items():
        section_total = sum(len(v) for v in categories.values())
        if section_total == 0:
            continue

        icon = SECTION_ICONS.get(section, "")
        lines.append(f"## {icon} {section}\n")

        for label, category_changes in categories.items():
            if not category_changes:
                continue

            lines.append(f"### {label} ({len(category_changes)})\n")

            for c in sorted(category_changes, key=change_sort_key):
                lines.extend(render_change_block(c, icon))

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_csv(changes, csv_path):

    fieldnames = [
        "report_section",
        "report_category",
        "change_id",
        "area",
        "change_type",
        "difference_category",
        "identifier",
        "section",
        "page",
        "old_page",
        "new_page",
        "preview",
        "display_title",
        "old_value",
        "new_value",
        "detail",
        "similarity",
    ]

    labels = bucket_labels()
    rows = []

    for change in changes:
        row = dict(change)
        report_section, report_category = labels.get(
            report_bucket(change), ("Critical Changes", "Requirement changes")
        )
        row["report_section"] = report_section
        row["report_category"] = report_category
        rows.append({fieldname: row.get(fieldname, "") for fieldname in fieldnames})

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(rows)


def write_json_report(
    changes, json_path, old_path, new_path, old_document, new_document
):

    report = {
        "comparison_created": datetime.now().isoformat(timespec="seconds"),
        "old_document": {
            "path": old_path,
            "document_name": old_document.get("document_name"),
            "total_pages": old_document.get("total_pages"),
        },
        "new_document": {
            "path": new_path,
            "document_name": new_document.get("document_name"),
            "total_pages": new_document.get("total_pages"),
        },
        "summary": summarise_changes(changes),
        "organized_changes": organise_changes(changes),
        "changes": changes,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def summarise_changes(changes):

    summary = {
        "total_changes": len(changes),
        "by_area": {},
        "by_change_type": {},
        "by_difference_category": {},
    }

    for change in changes:

        for summary_key, change_key in [
            ("by_area", "area"),
            ("by_change_type", "change_type"),
            ("by_difference_category", "difference_category"),
        ]:
            value = change.get(change_key)
            summary[summary_key][value] = summary[summary_key].get(value, 0) + 1

    return summary


def run_comparison(old_json, new_json, output_dir=OUTPUT_DIR, filename_prefix=None):
    """Compare two extracted specifications and return report data plus file paths."""

    ensure_output_dir(output_dir)

    old_document, old_path = load_json(old_json)
    new_document, new_path = load_json(new_json)

    changes = compare_documents(old_document, new_document)

    prefix = filename_prefix or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    csv_path = os.path.join(output_dir, f"version_differences_{prefix}.csv")
    json_path = os.path.join(output_dir, f"version_differences_{prefix}.json")
    md_path = os.path.join(output_dir, f"version_differences_{prefix}.md")

    write_csv(changes, csv_path)

    write_json_report(
        changes,
        json_path,
        old_path,
        new_path,
        old_document,
        new_document,
    )

    write_markdown_report(
        changes,
        md_path,
        old_path,
        new_path,
        old_document,
        new_document,
    )

    with open(json_path, "r", encoding="utf-8") as report_file:
        report = json.load(report_file)

    return {
        "report": report,
        "output_files": {
            "csv": str(csv_path),
            "json": str(json_path),
            "markdown": str(md_path),
        },
    }


def run_design_tool(old_json, new_json):
    """Compatibility wrapper retained for the original desktop integration."""

    result = run_comparison(old_json, new_json)
    files = result["output_files"]
    report = result["report"]
    log = f"""Comparison Complete

Old: {report['old_document']['path']}
New: {report['new_document']['path']}
Total Changes: {report['summary']['total_changes']}

CSV:
{files['csv']}

JSON:
{files['json']}

Markdown:
{files['markdown']}
"""

    return log, files["markdown"]


# ==========================================================
# RUN
# ==========================================================


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Compare two engineering specification JSON files "
            "created by Extractor(JSON UPDATED).py"
        )
    )

    parser.add_argument(
        "old_json",
        help="Path to the old document.json file, or a folder containing document.json",
    )

    parser.add_argument(
        "new_json",
        help="Path to the new document.json file, or a folder containing document.json",
    )

    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIR,
        help="Folder where the CSV and JSON comparison reports will be written",
    )

    parser.add_argument(
        "--csv-name", default=DEFAULT_CSV_NAME, help="Name of the CSV output file"
    )

    parser.add_argument(
        "--json-name", default=DEFAULT_JSON_NAME, help="Name of the JSON output file"
    )

    parser.add_argument(
        "--md-name", default=DEFAULT_MD_NAME, help="Name of the Markdown output file"
    )

    args = parser.parse_args()

    ensure_output_dir(args.output_dir)

    old_document, old_path = load_json(args.old_json)
    new_document, new_path = load_json(args.new_json)

    changes = compare_documents(old_document, new_document)

    csv_path = os.path.join(args.output_dir, args.csv_name)

    json_path = os.path.join(args.output_dir, args.json_name)

    md_path = os.path.join(args.output_dir, args.md_name)

    write_csv(changes, csv_path)

    write_json_report(
        changes, json_path, old_path, new_path, old_document, new_document
    )

    write_markdown_report(
        changes, md_path, old_path, new_path, old_document, new_document
    )

    print("\n===================================")
    print("VERSION COMPARISON COMPLETE")
    print("===================================")
    print("Old JSON:", old_path)
    print("New JSON:", new_path)
    print("Total changes:", len(changes))
    print("CSV:", csv_path)
    print("JSON:", json_path)
    print("Markdown:", md_path)


if __name__ == "__main__":

    main()
