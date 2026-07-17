"""Deterministic PDF-to-JSON extraction for engineering specifications.

The extractor intentionally uses layout and language rules rather than an LLM.
This makes results repeatable, but it also means engineers should review the
output and use the quality checker before treating it as complete.
"""

import json
from pathlib import Path
import re

import pandas as pd

try:
    # Current PyMuPDF releases expose this explicit package name.
    import pymupdf as fitz
except ImportError:
    try:
        # Older releases commonly expose the historical ``fitz`` alias.
        import fitz  # type: ignore[no-redef]
    except ImportError as error:
        raise RuntimeError(
            "PDF extraction requires PyMuPDF. Install it in the active backend "
            "environment with: python -m pip install pymupdf"
        ) from error

from Backend.Extraction.regex_patterns import (
    DECLARATIVE_BEHAVIOUR_REGEX,
    SECTION_REGEX,
    VALID_VPLAN_SECTION_REGEX,
    TABLE_REGEX,
    TABLE_REF_REGEX,
    FEATURE_REGEX,
    REQUIREMENT_REGEX,
    NOTE_REGEX,
    ACRONYM_REGEX,
    SECTION_REF_REGEX,
    ENCODING_TABLE_REGEX,
)

# ==========================================================
# ACRONYM STOPLIST
# ==========================================================
ACRONYM_STOPLIST = {
    "THE", "AND", "FOR", "WITH", "FROM", "THIS", "THAT",
    "ARE", "NOT", "BUT", "ITS", "ALL", "ANY", "CAN",
    "HAS", "HAVE", "BEEN", "WILL", "MAY", "SHALL", "MUST",
    "WHEN", "THEN", "EACH", "SUCH", "BOTH", "ALSO", "INTO",
    "OVER", "UPON", "USED", "ONLY", "MORE", "THAN", "BEEN",
    "WHICH", "THERE", "THEIR", "THESE", "THOSE", "WHAT",
    "PAGE", "NOTE", "TYPE", "DATA", "BASE", "TRUE", "FALSE"
}

# ==========================================================
# METADATA
# ==========================================================

def extract_document_metadata(pdf):
    metadata = pdf.metadata or {}
    return {
        "title":             metadata.get("title"),
        "author":            metadata.get("author"),
        "subject":           metadata.get("subject"),
        "keywords":          metadata.get("keywords"),
        "creator":           metadata.get("creator"),
        "producer":          metadata.get("producer"),
        "creation_date":     metadata.get("creationDate"),
        "modification_date": metadata.get("modDate")
    }

# ==========================================================
# HEADING EXTRACTION
# ==========================================================

def remove_detected_headings(text, headings):
    clean_text = text

    for h in headings:
        title = h.get("title", "").strip()
        section_id = h.get("section_id", "").strip()

        if section_id:
            clean_text = re.sub(
                rf'^\s*{re.escape(section_id)}\s+.*$',
                '',
                clean_text,
                flags=re.MULTILINE
            )

        if title:
            clean_text = re.sub(
                rf'^\s*{re.escape(title)}\s*$',
                '',
                clean_text,
                flags=re.MULTILINE
            )

    return clean_text

def extract_tables(page, page_num, table_folder, file_prefix, section_id=None):
    tables_found = []
    table_requirements = []
    try:
        tables = page.find_tables()
        for idx, table in enumerate(tables.tables):
            try:
                extracted = table.extract()
                if not extracted:
                    continue

                df = pd.DataFrame(extracted)
                csv_name = f"{file_prefix}_table_p{page_num+1}_{idx+1}.csv"
                csv_path = table_folder / csv_name
                df.to_csv(csv_path, index=False)
                tables_found.append({
                    "page":     page_num + 1,
                    "csv_file": str(csv_path)
                })
                
                for row in extracted:
                    cells = [
                        str(cell).replace("\n", " ").strip()
                        for cell in row
                        if cell and str(cell).strip()
                    ]

                    if len(cells) < 2:
                        continue

                    row_text = " ".join(cells)
    
                    if REQUIREMENT_REGEX.search(row_text) or FEATURE_REGEX.search(row_text):
                        table_requirements.append(
                            make_requirement(
                                None,
                                row_text,
                                section_id,
                                "table_requirement"
                            )
                        )

            except Exception as e:
                print(f"Table extraction error page {page_num+1}:", e)
    except Exception:
        pass
    return tables_found, table_requirements


def extract_encoding_table_requirements(text, section_id=None):
    requirements = []

    # pattern = re.compile(
    #     r'(0b[01]+)\s+'
    #     r'([A-Za-z][A-Za-z0-9_-]*)\s+'
    #     r'(.*?)'
    #     r'(?='
    #         r'\s+0b[01]+\s+[A-Za-z][A-Za-z0-9_-]*\s+'
    #         r'|\s+(?:\d+(?:\.\d+)*|[A-C]\d+(?:\.\d+)*)\s+'
    #         r'|\s+[A-C]\d+(?:\.\d+)+\s+[A-Za-z]'
    #         r'|\s+Table\s+[A-Za-z]?\d+(?:\.\d+)*'
    #         r'|\s+ARM IHI'
    #         r'|$'
    #     r')',
    #     re.DOTALL
    # )

    for code, operation, meaning in ENCODING_TABLE_REGEX.findall(text):
        meaning = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', meaning)
        meaning = re.sub(r'\s+', ' ', meaning).strip()

        if REQUIREMENT_REGEX.search(meaning) or FEATURE_REGEX.search(meaning):
            requirements.append(
                make_requirement(
                    None,
                    f"{code} | {operation} | {meaning}",
                    section_id,
                    "encoding_rule"
                )
            )

    return requirements

# ==========================================================
# TEXT ANALYSIS
# ==========================================================

def is_chapter_cover_page(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    
    if lines and re.match(r'^Chapter\s+[A-Z]\d+', lines[0]):
        if len(lines) > 1 and not lines[1].startswith("A"):
            if sum(
                bool(re.match(r'^•?\s*A\d+\.\d+', l))
                for l in lines
            ) >= 3:
                return True
    return False


def extract_headings_from_layout(layout):
    """
    Walk every text span in the page layout dict.
    A line is a heading if it matches SECTION_REGEX (now fixed to
    catch numeric sections like "2.3 Channel Signals").
    Font-size guard removed — the regex is specific enough that
    false positives are unlikely, and some AXI headings use body-
    size fonts in the appendix.
    """
    headings = []
    for block in layout.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(span["text"] for span in spans).strip()
            if re.search(r'\.{3,}\s*\d+$', text):
                continue
            
            if re.fullmatch(r'\d+', text):
                continue

            if not text:
                continue
            match = SECTION_REGEX.match(text)
            if match:
                sid = match.group(1)

                if not VALID_VPLAN_SECTION_REGEX.fullmatch(sid):
                    continue

                headings.append({
                    "section_id": sid,
                    "title": match.group(2),
                    "font_size": max(span["size"] for span in spans)
                })
    return headings


def classify_requirement(text):
    lower = text.lower()
    if any(x in lower for x in ["latency", "throughput", "timing",
                                  "frequency", "bandwidth"]):
        return "Performance"
    if any(x in lower for x in ["voltage", "current", "power"]):
        return "Electrical"
    if any(x in lower for x in ["temperature", "humidity"]):
        return "Environmental"
    if any(x in lower for x in ["safety", "hazard", "fault"]):
        return "Safety"
    if any(x in lower for x in ["interface", "spi", "uart", "i2c", "can"]):
        return "Interface"
    return "Functional"



def extract_signals(text):
    return sorted(set(re.findall(r'\b[A-Z][A-Z0-9_]{2,}\b', text)))


def make_requirement(req_id, text, section_id, category):
    return {
        "id": req_id,
        "text": text,
        "source_section": section_id,
        "signals": extract_signals(text),
        "type": category
    }

def requirement_text_key(text):
    """Create a consistent comparison key for requirement text."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def assign_unique_requirement_ids(requirements):
    section_counters = {}
    assigned_ids = set()

    for requirement in requirements:
        raw_section = requirement.get("source_section") or "UNKNOWN"

        section = re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            str(raw_section)
        ).strip("_")

        if not section:
            section = "UNKNOWN"

        section_counters[section] = section_counters.get(section, 0) + 1

        req_id = (
            f"REQ_{section}_"
            f"{section_counters[section]:03d}"
        )

        if req_id in assigned_ids:
            raise ValueError(
                f"Duplicate requirement ID generated: {req_id}"
            )

        requirement["id"] = req_id
        assigned_ids.add(req_id)

    return requirements

def is_vplan_relevant(line):
    line = " ".join(line.split()).strip()

    if not line:
        return False

    if re.search(
        r'\b(?:Figure|Fig\.?)\s+[A-Za-z]?\d+(?:\.\d+)*',
        line,
        re.IGNORECASE
    ):
        return False

    if re.match(
        r'^(?:'
        r'In Figure|'
        r'As shown in Figure|'
        r'The figure shows|'
        r'This assertion indicates|'
        r'In this case|'
        r'For example'
        r')\b',
        line,
        re.IGNORECASE
    ):
        return False
    
     # Existing high-confidence requirement detection
    if REQUIREMENT_REGEX.search(line):
        return True
    
    if DECLARATIVE_BEHAVIOUR_REGEX.search(line):
        return True
    
    return False

    # return REQUIREMENT_REGEX.search(line) is not None

def extract_requirements(text, section_id=None):
    requirements = []

    lines = [
        line for line in text.splitlines()
        if not re.match(r'^\s*(Figure|Table)\s+', line, re.IGNORECASE)
    ]

    text = "\n".join(lines)

    clean_text = " ".join(text.split())

    clean_text = re.sub(
        r'Figure\s+[A-Za-z]?\d+(?:\.\d+)*:\s*[^\n.]*',
        '',
        clean_text,
        flags=re.IGNORECASE
    )

    clean_text = re.sub(
        r'Table\s+[A-Za-z]?\d+(?:\.\d+)*:\s*[^\n.]*',
        '',
        clean_text,
        flags=re.IGNORECASE
    )

    clean_text = re.sub(
        r'(?:\b\d+\s+){3,}[A-Z][A-Z\s]{10,}',
        '',
        clean_text
    )

    clean_text = re.sub(
        r'(Must use an ID that is unique in-flight on the same channels:)\s*•',
        r'\1 •',
        clean_text
    )

    clean_text = re.sub(
        r'(Must not use the same ID for in-flight transactions on the same channels:)\s*•',
        r'\1 •',
        clean_text
    )

    clean_text = re.sub(
        r'(Must use the same ID:)\s*•',
        r'\1 •',
        clean_text
    )

    sentences = re.split(r'(?=•)|(?<=[.!?])\s+', clean_text)

    raw_sentences = re.split(r'(?=•)|(?<=[.!?])\s+', clean_text)

    sentences = []
    current_parent = ""

    for s in raw_sentences:
        s = s.strip()

        # parent line = contains requirement language and ends with ":"
        if s.endswith(":") and REQUIREMENT_REGEX.search(s):
            # keep only from the first requirement word, remove merged heading before it
            m = re.search(r'\b(Must|Must not|Shall|Should|Cannot|Can|May|If|When|The)\b', s, re.IGNORECASE)
            if m:
                current_parent = s[m.start():]
            else:
                current_parent = s
            continue

        if s.startswith("•") and current_parent:
            s = current_parent + " " + s

        sentences.append(s)


    for line in sentences:
        line = line.strip()

        line = re.sub(
            r'^[A-Z][A-Za-z0-9\- ]{2,80}\s*[–-]\s*(?=(If|When|The|A|An|For|It)\b)',
            '',
            line
        ).strip()
        
        line = re.sub(
            r'^(Name\s+Width\s+Default\s+Description\s+)+',
            '',
            line,
            flags=re.IGNORECASE
        ).strip()

        if re.match(
            r'^[A-Z0-9_, ]+\s+(?:are|is)\s+(?:present|not present)\.?$',
            line,
            re.IGNORECASE
        ):
            continue

        # line = re.sub(r'^•\s*', '', line)
        line = re.sub(r'•\s*', '', line)

        line = re.sub(
            r'^.*?The required behavior .*?:\s*',
            '',
            line,
            flags=re.IGNORECASE
        )

        line = re.sub(
            r'^[A-Z0-9_, ]+\s+\d+\s+0x[0-9A-Fa-f]+\s+',
            '',
            line
        ).strip()

        if not line:
            continue

        if line.endswith(":"):
            continue

        if re.match(
            r'^(?:Name|Width|Default|Description)(?:\s+\w+){2,}$',
            line
        ):
            continue

        if re.match(r'^.*This section describes .*$', line):
            continue

        if (
            re.match(r'^[A-C]\d+(?:\.\d+)*\s+', line)
            and not REQUIREMENT_REGEX.search(line)
        ):
            continue

        if re.match(r'^\[\d+\]\s+', line):
            continue

        if line.startswith("Table "):
            continue

        if re.match(r'^[A-C]\d+(?:\.\d+)*\s+', line):
            continue

        if line.startswith("In this specification"):
            continue

        if line.lower().endswith("can either:"):
            continue
        if re.match(r'^[A-Z][A-Za-z ]+\s+[A-C]\d+(?:\.\d+)*\.?$', line):
            continue

        if re.match(r'^Chapter\s+[A-Z]\d+\.?$', line):
            continue

        if line.startswith("ARM IHI"):
            continue

        if "Copyright" in line:
            continue

        if line == "All rights reserved.":
            continue

        if re.match(r'^Non-confidential\s+\d+$', line):
            continue

        if line.startswith("See "):
            continue

        if line.lower().startswith("however,"):
            continue

        # if REQUIREMENT_REGEX.search(line) or FEATURE_REGEX.search(line):
        if is_vplan_relevant(line):
            requirements.append(
                make_requirement(
                    # req_id,
                    None,
                    line,
                    section_id,
                    "protocol_rule"
                )
            )

    return requirements

def extract_notes(text):
    notes = []
    for line in text.splitlines():
        line = line.strip()
        if NOTE_REGEX.match(line):
            kind = line.split(":")[0].upper()
            notes.append({"type": kind, "text": line})
    return notes


def extract_acronyms(text):
    """
    FIX 3 applied here: after collecting uppercase tokens we filter
    against ACRONYM_STOPLIST to remove common English words that
    happen to be all-caps (THE, AND, FOR, etc.).
    """
    found = set()
    for match in ACRONYM_REGEX.finditer(text):
        word = match.group(1)
        # len > 1 was the original guard; we strengthen it to > 1
        # AND not in the stoplist.
        if len(word) > 1 and word not in ACRONYM_STOPLIST:
            found.add(word)
    return sorted(found)


def extract_cross_references(text):
    """
    FIX 2 applied here.
    ORIGINAL used SECTION_REF_REGEX with a capturing group, so
    findall returned partial strings like ".3" instead of
    "Section 2.3".  Now that the regex is non-capturing, findall
    correctly returns the full matched strings.
    """
    refs = []
    refs.extend(SECTION_REF_REGEX.findall(text))   # now returns full match
    # refs.extend(FIGURE_REF_REGEX.findall(text))
    refs.extend(TABLE_REF_REGEX.findall(text))
    return refs


def build_section_tree(headings):
    sections = []
    for h in headings:
        sid = h["section_id"]
        parent = sid.rsplit(".", 1)[0] if "." in sid else None
        sections.append({
            "id":     sid,
            "title":  h["title"],
            "parent": parent
        })
    return sections


# ==========================================================
# SEMANTIC CHUNKS — rebuilt as section-level, not page-level
# ==========================================================

def build_semantic_chunks(pages):
    """
    Walk the already-processed page list and merge text by section.
    When the section changes (a new heading was detected), flush the
    current buffer as a completed chunk and start a new one.
    Pages with no heading inherit the most recent section (same
    behaviour as before, just accumulated rather than emitted).
    """
    chunks = []
    current_section = None
    buffer = []

    for page in pages:
        # If this page introduced new headings, flush the current buffer
        if page["headings"]:
            if buffer and current_section is not None:
                chunks.append({
                    "section": current_section,
                    "text":    "\n".join(buffer).strip()
                })
            buffer = []
            current_section = page["headings"][-1]["section_id"]

        buffer.append(page["text"])

    # Flush the last section
    if buffer and current_section is not None:
        chunks.append({
            "section": current_section,
            "text":    "\n".join(buffer).strip()
        })

    return chunks


# ==========================================================
# CAPTION EXTRACTORS
# ==========================================================

def is_valid_vplan_section(section):
    if section is None:
        return False
    return VALID_VPLAN_SECTION_REGEX.match(str(section)) is not None

def extract_table_captions(text):
    tables = []
    for line in text.splitlines():
        line = line.strip()
        if TABLE_REGEX.match(line):
            tables.append({"caption": line})
    return tables

def extract_heading_from_text(text):
    for line in text.splitlines()[:80]:
        line = line.strip()

        if not line:
            continue

        if line.lower().startswith("chapter"):
            continue

        if re.search(r'\.{3,}\s*\d+$', line):
            continue

        if re.fullmatch(r'\d+', line):
            continue

        match = SECTION_REGEX.match(line)

        if match:
            sid = match.group(1)
            title = match.group(2).strip()

            # if not re.match(r'^[A-C]\d+(?:\.\d+)*$', sid):
            #     continue

            if not VALID_VPLAN_SECTION_REGEX.fullmatch(sid):
                continue

            if len(title) < 3:
                continue

            return {
                "section_id": sid,
                "title": title,
                "font_size": None
            }

    return None

def normalize(text):
    return re.sub(r'[\W_]+', '', text).lower()
# ==========================================================
# MAIN PARSER
# ==========================================================

def parse_pdf(
    pdf_path: str | Path,
    output_dir: str | Path,
    *,
    output_stem: str | None = None,
    document_name: str | None = None,
) -> dict:
    """Extract a PDF and write both full-document and requirements-only JSON.

    ``output_dir`` is supplied by the API from the shared path configuration;
    the extractor never relies on the process working directory.
    """

    source_path = Path(pdf_path)
    destination = Path(output_dir)
    table_folder = destination / "tables"
    raw_prefix = output_stem or source_path.stem
    file_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_prefix).strip("_.")
    if not file_prefix:
        file_prefix = "extraction"
    destination.mkdir(parents=True, exist_ok=True)
    table_folder.mkdir(parents=True, exist_ok=True)

    pdf = fitz.open(source_path)

    # Uncomment to also render full-page PNGs:
    # save_page_screenshots(pdf_path, PAGE_FOLDER)

    # image_records = extract_images(pdf)

    document = {
        "document_name":    document_name or source_path.name,
        "metadata":         extract_document_metadata(pdf),
        "total_pages":      len(pdf),
        "sections":         [],
        "requirements":     [],
        "figures":          [],
        "tables":           [],
        "notes":            [],
        "acronyms":         [],
        "cross_references": [],
        "semantic_chunks":  [],
        "pages":            []
    }

    print("\nProcessing pages...")

    current_section = None
    seen_requirement_texts = set()
    
    for page_num in range(len(pdf)):

        page   = pdf[page_num]
        layout = page.get_text("dict")
        text   = page.get_text("text")

        headings = extract_headings_from_layout(layout)

        text_heading = extract_heading_from_text(text)

        if text_heading:
            headings = [text_heading]

        if not headings:
            for line in text.splitlines()[:20]:
                line = line.strip()

                # skip chapter/page headers
                if line.lower().startswith("chapter"):
                    continue

                match = SECTION_REGEX.match(line)
                if match:
                    sid = match.group(1)

                    if not VALID_VPLAN_SECTION_REGEX.fullmatch(sid):
                        continue

                    headings = [{
                        "section_id": sid,
                        "title": match.group(2),
                        "font_size": None
                    }]
                    break

        if headings:
            current_section = headings[-1]["section_id"]
        elif current_section is None:
            current_section = "Unknown"

        is_cover = is_chapter_cover_page(text)

        if is_cover:
            requirements = []
            table_reqs = []
        else:
            # requirements = extract_requirements(text, current_section)
            clean_text = remove_detected_headings(text, headings)
            requirements = extract_requirements(clean_text, current_section)
            table_reqs = extract_encoding_table_requirements(clean_text, current_section)

        if table_reqs:
            requirements = [
                r for r in requirements
                if not (
                    "as shown in Table" in r["text"]
                    or "Operation Meaning" in r["text"]
                    or re.match(r'^0b[01]+', r["text"])
                    or any(
                        normalize(r["text"]) in normalize(tr["text"])
                        or normalize(tr["text"]) in normalize(r["text"])
                        for tr in table_reqs
                    )
                )
            ]

        requirements.extend(table_reqs)


        notes         = extract_notes(text)
        acronyms      = extract_acronyms(text)
        cross_refs    = extract_cross_references(text)
        table_captions = extract_table_captions(text)
        extracted_tables, table_requirements = extract_tables(
            page,
            page_num,
            table_folder,
            file_prefix,
            current_section,
        )
        requirements.extend(table_requirements)

        # De-duplicate after all text and table rules have contributed records.
        unique_page_requirements = []
        for requirement in requirements:
            key = requirement_text_key(requirement["text"])
            if key in seen_requirement_texts:
                continue
            seen_requirement_texts.add(key)
            unique_page_requirements.append(requirement)
        requirements = unique_page_requirements

        page_json = {
            "page_number":   page_num + 1,
            "text":          text,
            "headings":      headings,
            "figures":       [],
            "table_captions": table_captions,
            "tables":        extracted_tables,
            "images":        [],
        }

        for req in requirements:
            req["source_page"] = page_num + 1

        document["requirements"].extend(requirements)
        document["notes"].extend(notes)
        document["acronyms"].extend(acronyms)
        document["cross_references"].extend(cross_refs)
        document["tables"].extend(extracted_tables)
        document["pages"].append(page_json)

        print(f"Processed page {page_num+1}/{len(pdf)}")

    assign_unique_requirement_ids(document["requirements"])

    # ----------------------------------------------------------
    # Post-processing: build section tree and semantic chunks
    # ----------------------------------------------------------

    all_headings = []
    for p in document["pages"]:
        all_headings.extend(p["headings"])
    document["sections"] = build_section_tree(all_headings)

    # FIX 5: section-level chunks built from all pages at once
    document["semantic_chunks"] = build_semantic_chunks(document["pages"])

    # Deduplicate acronyms (unchanged)
    document["acronyms"] = sorted(set(document["acronyms"]))
    

    # ----------------------------------------------------------
    # Random page checks for manual requirement validation
    # ----------------------------------------------------------

    # NUM_RANDOM_CHECKS = 1

    # print("\n===================================")
    # print("RANDOM PAGE REQUIREMENT CHECKS")
    # print("===================================")

    # random_pages = rand.sample(
    #     document["pages"],
    #     min(NUM_RANDOM_CHECKS, len(document["pages"]))
    # )

    # for p in random_pages:
    #     print("\n" + "=" * 80)
    #     print(f"PAGE {p['page_number']}")
    #     print("=" * 80)

    #     print("\nRequirements:")
    #     if p["requirements"]:
    #         for r in p["requirements"]:
    #             print("-", r["text"])
    #     else:
    #         print("- None found")

    #     print("\nPage text preview:")
    #     print(p["text"][:1500])                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         

    # ----------------------------------------------------------
    # Write JSON
    # ----------------------------------------------------------

    json_path = destination / f"{file_prefix}_document.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(document, f, indent=2, ensure_ascii=False)

    print("\n===================================")
    print("PARSING COMPLETE")
    print("===================================")
    print("JSON:    ", json_path)
    print("Tables:  ", table_folder)

    pdf.close()

    return {
        "document": document,
        "document_path": json_path,
        "table_paths": [Path(item["csv_file"]) for item in document["tables"]],
    }
