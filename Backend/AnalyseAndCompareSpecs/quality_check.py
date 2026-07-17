"""
Quality checker for engineering specification extractor outputs.

The checker reports three final percentages and pass/fail labels:

1. Completeness percentage
   Formula:
       completeness = mean(
           required_json_field_score,
           page_coverage_score,
           text_coverage_score,
           semantic_chunk_coverage_score,
           record_field_completeness_score,
           cross_reference_recall_score,
           requirement_recall_score
       )

2. Accuracy percentage
   Formula without a gold/reference JSON:
       accuracy = mean(
           page_text_fidelity_score,
           requirement_traceability_score,
           category_consistency_score,
           page_number_accuracy_score,
           json_internal_consistency_score
       )

   Formula with --gold-json: can input a gold reference document to use for quality check
       accuracy = mean(
           requirement_f1_score,
           figure_caption_f1_score,
           table_caption_f1_score,
           page_text_fidelity_score,
           json_internal_consistency_score
       )

3. Table/figure capture percentage
   Formula:
       table_figure_capture = mean(
           table_detection_f1_score,
           table_caption_f1_score,
           table_file_existence_score,
           figure_caption_f1_score,
           image_capture_f1_score
       )

Each percentage is marked "pass" if it is >= --threshold, otherwise "fail".
The default threshold is 95%.
"""

from __future__ import annotations

from Backend.AnalyseAndCompareSpecs.regex_patterns import (
    VALID_VPLAN_SECTION_REGEX,
    TABLE_REF_REGEX,
    SECTION_REF_REGEX,
    REQUIREMENT_REGEX,
)


import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover - compatibility with older PyMuPDF
    try:
        import fitz
    except ImportError:  # pragma: no cover - handled when PDF checks are requested
        fitz = None


REQUIRED_TOP_LEVEL_KEYS = {
    "document_name",
    "metadata",
    "total_pages",
    "sections",
    "requirements",
    "figures",
    "tables",
    "notes",
    "acronyms",
    "cross_references",
    "semantic_chunks",
    "pages",
}

CATEGORY_KEYWORDS = {
    "Performance": [
        "latency",
        "throughput",
        "timing",
        "frequency",
        "bandwidth",
        "clock rate",
        "cycles per",
        "ipc",
        "mhz",
        "ghz",
        "performance",
    ],
    "Electrical": [
        "voltage",
        "current",
        "power",
        "vdd",
        "vcc",
        "vref",
        "amperage",
        "watt",
        "dissipation",
        "impedance",
    ],
    "Environmental": [
        "temperature",
        "humidity",
        "thermal",
        "esd",
        "altitude",
        "vibration",
    ],
    "Safety": [
        "safety",
        "hazard",
        "fault",
        "asil",
        "functional safety",
        "redundant",
        "ecc",
        "parity",
        "error correction",
        "watchdog",
    ],
    "Security": [
        "encryption",
        "authentication",
        "secure boot",
        "pmp",
        "tee",
        "cryptograph",
        "attestation",
        "tamper",
    ],
    "Protocol": [
        "axi",
        "amba",
        "ahb",
        "apb",
        "ace",
        "chi",
        "tilelink",
        "burst",
        "handshake",
        "arvalid",
        "awvalid",
        "wready",
        "bvalid",
        "arbiter",
        "master",
        "slave",
        "manager",
        "subordinate",
        "outstanding transaction",
        "beat",
        "strobe",
    ],
    "Memory": [
        "cache",
        "tlb",
        "mmu",
        "dram",
        "sram",
        "memory-mapped",
        "memory map",
        "address space",
        "page table",
        "coherenc",
        "physical address",
        "virtual address",
    ],
    "Architecture": [
        "instruction",
        "opcode",
        "register",
        "risc-v",
        "riscv",
        "isa",
        "extension",
        "privilege mode",
        "csr",
        "trap",
        "exception",
        "interrupt",
        "pipeline",
        "hart",
        "atomic",
        "vector unit",
    ],
    "Interface": [
        "interface",
        "pin",
        "signal",
        "spi",
        "uart",
        "i2c",
        "can",
        "gpio",
        "jtag",
        "pcie",
    ],
}

# "Functional" is the fallback category in classify_requirement() and has
# no keyword list of its own, so it's added here explicitly.
VALID_REQUIREMENT_CATEGORIES = set(CATEGORY_KEYWORDS.keys()) | {"Functional"}

FIGURE_REGEX = re.compile(
    r"\b(?:Figure|Fig\.?)\s+([A-Za-z]?\d+(?:[-.]\d+)*)", re.IGNORECASE
)
TABLE_REGEX = re.compile(r"(?:Table)\s+([A-Za-z]?\d+(?:[-.]\d+)*)", re.IGNORECASE)
CROSS_REF_REGEX = re.compile(
    r"^(Section|Table|Figure)\s+([A-Za-z]?\d+(?:[-.]\d+)*)$",
    re.IGNORECASE,
)

# Structural (pattern-based, not keyword-list-based) matchers for the two
# priority spec families. These generalize across new signal/CSR names
# without needing a growing hardcoded word list.
AXI_SIGNAL_REGEX = re.compile(
    r"\b[AR][RW](VALID|READY|LEN|SIZE|BURST|ID|ADDR|LOCK|CACHE|PROT|QOS|REGION)\b"
    r"|\b[RWB](VALID|READY|DATA|LAST|STRB|RESP|ID)\b",
    re.IGNORECASE,
)
RISCV_CSR_REGEX = re.compile(
    r"\b(mstatus|mtvec|mepc|mcause|mtval|mie|mip|mscratch|mideleg|medeleg|"
    r"satp|sstatus|stvec|sepc|scause|stval|sie|sip|sscratch|"
    r"pmpcfg\d*|pmpaddr\d*|misa|mhartid|"
    r"RV(?:32|64|128)[IEMAFDQC]*)\b",
    re.IGNORECASE,
)

# Tie-break order for classify_requirement_scored(): when a requirement
# scores equally across categories, prefer the priority spec families first.
PRIORITY_ORDER = [
    "Protocol",
    "Architecture",
    "Memory",
    "Security",
    "Safety",
    "Electrical",
    "Performance",
    "Environmental",
    "Interface",
]


def cross_references_resolve(document: dict[str, Any]) -> bool:
    cross_refs = document.get("cross_references", [])
    if not isinstance(cross_refs, list) or not cross_refs:
        return True

    section_numbers = {
        normalise_text(r.get("section"))
        for r in document.get("requirements", [])
        if isinstance(r, dict) and r.get("section")
    }

    table_numbers = set()
    for page in (
        document.get("pages", []) if isinstance(document.get("pages"), list) else []
    ):
        if not isinstance(page, dict):
            continue
        for cap in (
            page.get("table_captions", [])
            if isinstance(page.get("table_captions"), list)
            else []
        ):
            caption = cap.get("caption") if isinstance(cap, dict) else None
            if caption:
                m = TABLE_REGEX.match(str(caption).strip())
                if m:
                    table_numbers.add(normalise_text(m.group(1)))

    # Figures are not yet extracted reliably — skip figure refs rather than
    # penalize them until figure extraction is in place.
    lookup = {"section": section_numbers, "table": table_numbers}

    resolved = total = 0
    for ref in cross_refs:
        if not isinstance(ref, str):
            continue
        m = CROSS_REF_REGEX.match(ref.strip())
        if not m:
            continue
        ref_type, ref_num = m.group(1).lower(), normalise_text(m.group(2))
        if ref_type == "figure":
            continue  # skip — not counted toward total or resolved
        total += 1
        if ref_num in lookup[ref_type]:
            resolved += 1

    return total == 0 or resolved == total


@dataclass
class Score:
    name: str
    percentage: float
    formula: str
    details: dict[str, Any]


def normalise_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\uf05a", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def pct(numerator: float, denominator: float, *, empty_is: float = 100.0) -> float:
    if denominator == 0:
        return empty_is
    return max(0.0, min(100.0, 100.0 * numerator / denominator))


def mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 100.0
    return sum(values) / len(values)


def f1_from_counters(expected: Counter[str], captured: Counter[str]) -> float:
    expected_total = sum(expected.values())
    captured_total = sum(captured.values())
    if expected_total == 0 and captured_total == 0:
        return 100.0
    if expected_total == 0 or captured_total == 0:
        return 0.0

    true_positive = sum(
        min(expected[key], captured[key]) for key in expected.keys() | captured.keys()
    )
    precision = true_positive / captured_total if captured_total else 0.0
    recall = true_positive / expected_total if expected_total else 0.0
    if precision + recall == 0:
        return 0.0
    return 100.0 * (2 * precision * recall) / (precision + recall)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object at the top level")
    return data


def infer_pdf_path(json_path: Path, document: dict[str, Any]) -> Path | None:
    doc_name = document.get("document_name")
    candidates: list[Path] = []
    if isinstance(doc_name, str) and doc_name:
        candidates.append(json_path.parent / Path(doc_name).name)

    stem = json_path.stem.removesuffix(".json")
    if stem:
        candidates.append(json_path.parent / f"{stem}.pdf")

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def open_pdf(pdf_path: Path | None):
    if pdf_path is None:
        return None
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF is required for PDF-based checks. Install with: pip install pymupdf"
        )
    return fitz.open(str(pdf_path))


def pdf_page_texts(pdf) -> list[str]:
    if pdf is None:
        return []
    return [page.get_text("text") for page in pdf]


def expected_captions(page_texts: list[str], regex: re.Pattern[str]) -> Counter[str]:
    found: Counter[str] = Counter()

    for page_index, text in enumerate(page_texts, start=1):

        for line in text.splitlines():

            line = line.strip()

            if not line:
                continue

            if regex.match(line):
                found[f"{page_index}:{normalise_text(line)}"] += 1

    return found


def captured_captions(
    document: dict[str, Any], key: str, caption_key: str = "caption"
) -> Counter[str]:
    found: Counter[str] = Counter()
    for page in (
        document.get("pages", []) if isinstance(document.get("pages"), list) else []
    ):
        page_number = page.get("page_number")
        for item in page.get(key, []) if isinstance(page.get(key), list) else []:
            caption = item.get(caption_key) if isinstance(item, dict) else None
            if caption:
                found[f"{page_number}:{normalise_text(caption)}"] += 1
    return found


def page_count_counter(items: Iterable[Any], page_key: str = "page") -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        if isinstance(item, dict) and item.get(page_key) is not None:
            counts[str(item.get(page_key))] += 1
    return counts


def expected_table_counts(pdf) -> Counter[str]:
    counts: Counter[str] = Counter()
    if pdf is None:
        return counts
    for page_index, page in enumerate(pdf, start=1):
        try:
            tables = page.find_tables()
            table_count = len(tables.tables)
            if table_count:
                counts[str(page_index)] = table_count
        except Exception:
            continue
    return counts


def expected_image_counts(pdf) -> Counter[str]:
    counts: Counter[str] = Counter()
    if pdf is None:
        return counts
    for page_index, page in enumerate(pdf, start=1):
        try:
            image_count = len(page.get_images(full=True))
            if image_count:
                counts[str(page_index)] = image_count
        except Exception:
            continue
    return counts


def all_page_requirements(document: dict[str, Any]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    pages = document.get("pages", [])
    if not isinstance(pages, list):
        return requirements
    for page in pages:
        page_number = page.get("page_number") if isinstance(page, dict) else None
        for req in (
            page.get("requirements", [])
            if isinstance(page.get("requirements"), list)
            else []
        ):
            if isinstance(req, dict):
                copied = dict(req)
                copied["_page_number"] = page_number
                requirements.append(copied)
    return requirements


def requirement_counter(requirements: Iterable[dict[str, Any]]) -> Counter[str]:
    values: Counter[str] = Counter()
    for req in requirements:
        text = normalise_text(req.get("text"))
        category = normalise_text(req.get("category"))
        if text:
            values[f"{category}|{text}"] += 1
    return values


def classify_requirement(text: str) -> str:
    lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(word in lower for word in keywords):
            return category
    return "Functional"


def classify_requirement_scored(text: str) -> str:
    """Companion to classify_requirement(): scores every category by keyword
    hit count, boosts Protocol/Architecture using structural AXI/RISC-V
    regex matches (no new keyword list needed), and breaks ties using
    PRIORITY_ORDER so AXI/RISC-V-relevant categories win ambiguous cases.
    Does not replace classify_requirement() - used as an additional signal.
    """
    lower = text.lower()
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for word in keywords if word in lower)
        if hits:
            scores[category] = hits

    if AXI_SIGNAL_REGEX.search(text):
        scores["Protocol"] = scores.get("Protocol", 0) + 2
    if RISCV_CSR_REGEX.search(text):
        scores["Architecture"] = scores.get("Architecture", 0) + 2

    if not scores:
        return "Functional"

    best = max(scores.values())
    tied = [category for category, value in scores.items() if value == best]
    if len(tied) == 1:
        return tied[0]
    for category in PRIORITY_ORDER:
        if category in tied:
            return category
    return tied[0]


def requirement_recall_score(
    pdf_page_texts_value: list[str], top_requirements: list[dict]
) -> float:
    expected_sentences = 0
    for text in pdf_page_texts_value:
        for line in text.splitlines():
            if REQUIREMENT_REGEX.search(line):
                expected_sentences += 1
    if expected_sentences == 0:
        return 100.0
    return pct(len(top_requirements), expected_sentences)


def section_format_valid(requirements: list[dict]) -> bool:
    sections = [
        r.get("section")
        for r in requirements
        if isinstance(r, dict) and r.get("section")
    ]
    if not sections:
        return True
    return all(VALID_VPLAN_SECTION_REGEX.match(str(s)) for s in sections)


def axi_signal_fidelity_score(
    pdf_page_texts_value: list[str], top_requirements: list[dict]
) -> float:
    """F1 between AXI signal tokens (ARVALID, WREADY, etc.) mentioned in the
    source PDF vs. tokens preserved in extracted requirement text. Self
    neutralizes to 100 on non-AXI documents (empty source token set), so it
    adds signal only where it's relevant without penalizing other specs."""
    source_text = "\n".join(pdf_page_texts_value)
    source_tokens = Counter(
        m.group(0).upper() for m in AXI_SIGNAL_REGEX.finditer(source_text)
    )
    if not source_tokens:
        return 100.0
    req_text = " ".join(
        str(r.get("text"))
        for r in top_requirements
        if isinstance(r, dict) and r.get("text")
    )
    captured_tokens = Counter(
        m.group(0).upper() for m in AXI_SIGNAL_REGEX.finditer(req_text)
    )
    return f1_from_counters(source_tokens, captured_tokens)


def riscv_csr_fidelity_score(
    pdf_page_texts_value: list[str], top_requirements: list[dict]
) -> float:
    """F1 between RISC-V CSR/ISA tokens (mstatus, satp, RV32I, etc.) mentioned
    in the source PDF vs. tokens preserved in extracted requirement text.
    Self neutralizes to 100 on non-RISC-V documents."""
    source_text = "\n".join(pdf_page_texts_value)
    source_tokens = Counter(
        m.group(0).upper() for m in RISCV_CSR_REGEX.finditer(source_text)
    )
    if not source_tokens:
        return 100.0
    req_text = " ".join(
        str(r.get("text"))
        for r in top_requirements
        if isinstance(r, dict) and r.get("text")
    )
    captured_tokens = Counter(
        m.group(0).upper() for m in RISCV_CSR_REGEX.finditer(req_text)
    )
    return f1_from_counters(source_tokens, captured_tokens)


def cross_reference_recall_score(
    pdf_page_texts_value: list[str], cross_refs: list
) -> float:
    all_text = "\n".join(pdf_page_texts_value)
    expected = {normalise_text(m) for m in SECTION_REF_REGEX.findall(all_text)} | {
        normalise_text(m) for m in TABLE_REF_REGEX.findall(all_text)
    }
    if not expected:
        return 100.0
    captured = {normalise_text(r) for r in cross_refs if isinstance(r, str)}
    return pct(len(expected & captured), len(expected))


def collect_covered_pages(document: dict[str, Any]) -> set[int]:
    covered_pages: set[int] = set()

    def add_page(value: Any) -> None:
        page_num = None
        if isinstance(value, int):
            page_num = value
        elif isinstance(value, str) and value.strip().lstrip("-").isdigit():
            page_num = int(value)
        if page_num is not None and page_num >= 1:
            covered_pages.add(page_num)

    def process_chunk(chunk: dict[str, Any]) -> None:
        pages_in_chunk = chunk.get("pages")
        if isinstance(pages_in_chunk, list):
            for p in pages_in_chunk:
                add_page(p)

        single_page = chunk.get("page")
        if single_page is not None:
            add_page(single_page)

        start, end = chunk.get("page_start"), chunk.get("page_end")
        if isinstance(start, int) and isinstance(end, int) and end >= start:
            covered_pages.update(range(start, end + 1))

    top_level_chunks = document.get("semantic_chunks", [])
    if isinstance(top_level_chunks, list):
        for chunk in top_level_chunks:
            if isinstance(chunk, dict):
                process_chunk(chunk)

    pages = document.get("pages", [])
    if isinstance(pages, list):
        for page in pages:
            if not isinstance(page, dict):
                continue
            nested_chunks = page.get("semantic_chunks", [])
            if isinstance(nested_chunks, list):
                for chunk in nested_chunks:
                    if isinstance(chunk, dict):
                        process_chunk(chunk)
                        if not any(k in chunk for k in ("pages", "page", "page_start")):
                            add_page(page.get("page_number"))

    return covered_pages


def score_completeness(
    document: dict[str, Any],
    pdf_page_texts_value: list[str],
) -> Score:
    required_json_field_score = pct(
        len(REQUIRED_TOP_LEVEL_KEYS.intersection(document.keys())),
        len(REQUIRED_TOP_LEVEL_KEYS),
    )

    pages = document.get("pages", [])
    pages = pages if isinstance(pages, list) else []
    expected_page_count = len(pdf_page_texts_value) or int(
        document.get("total_pages") or 0
    )
    page_coverage_score = pct(len(pages), expected_page_count)

    output_text_chars = sum(
        len(page.get("text", "")) for page in pages if isinstance(page, dict)
    )
    source_text_chars = sum(len(text) for text in pdf_page_texts_value)
    text_coverage_score = pct(
        min(output_text_chars, source_text_chars), source_text_chars
    )

    covered_pages = collect_covered_pages(document)
    semantic_chunk_coverage_score = pct(len(covered_pages), expected_page_count)

    top_requirements = document.get("requirements", [])
    top_requirements = top_requirements if isinstance(top_requirements, list) else []

    record_scores: list[float] = []

    for key, fields in {
        "requirements": {"text", "category"},
        "figures": {"caption"},
        "tables": {"page", "csv_file"},
    }.items():
        records = document.get(key, [])
        if not isinstance(records, list) or not records:
            continue
        checks = 0
        passed = 0
        for record in records:
            if not isinstance(record, dict):
                checks += len(fields)
                continue
            for field in fields:
                checks += 1
                if record.get(field) not in (None, ""):
                    passed += 1
        record_scores.append(pct(passed, checks))
    record_field_completeness_score = mean(record_scores)

    component_scores = {
        "required_json_field_score": required_json_field_score,
        "page_coverage_score": page_coverage_score,
        "text_coverage_score": text_coverage_score,
        "semantic_chunk_coverage_score": semantic_chunk_coverage_score,
        "record_field_completeness_score": record_field_completeness_score,
        "cross_reference_recall_score": cross_reference_recall_score(
            pdf_page_texts_value, document.get("cross_references", [])
        ),
        "requirement_recall_score": requirement_recall_score(
            pdf_page_texts_value, top_requirements
        ),
    }

    return Score(
        name="completeness",
        percentage=mean(component_scores.values()),
        formula="mean(required_json_field, page_coverage, text_coverage, semantic_chunk_coverage, record_field_completeness, cross_reference_recall, requirement_recall)",
        details=component_scores,
    )


def score_accuracy(
    document: dict[str, Any],
    pdf_page_texts_value: list[str],
    gold_document: dict[str, Any] | None,
) -> Score:
    pages = document.get("pages", [])
    pages = pages if isinstance(pages, list) else []

    fidelity_scores = []
    for index, source_text in enumerate(pdf_page_texts_value):
        output_text = (
            pages[index].get("text", "")
            if index < len(pages) and isinstance(pages[index], dict)
            else ""
        )
        fidelity_scores.append(
            100.0
            * SequenceMatcher(
                None, normalise_text(source_text), normalise_text(output_text)
            ).ratio()
        )
    page_text_fidelity_score = mean(fidelity_scores)

    top_requirements = document.get("requirements", [])
    top_requirements = top_requirements if isinstance(top_requirements, list) else []
    page_requirements = all_page_requirements(document)
    all_source_text = normalise_text("\n".join(pdf_page_texts_value))

    traceable = 0
    for req in top_requirements:
        text = normalise_text(req.get("text") if isinstance(req, dict) else "")
        if text and text in all_source_text:
            traceable += 1
    requirement_traceability_score = pct(traceable, len(top_requirements))

    category_matches = 0
    category_checks = 0
    for req in top_requirements:
        if not isinstance(req, dict):
            continue
        text = req.get("text")
        category = req.get("category")
        if text and category:
            category_checks += 1
            if (
                category == classify_requirement(str(text))
                and category in VALID_REQUIREMENT_CATEGORIES
            ):
                category_matches += 1
    category_consistency_score = pct(category_matches, category_checks)

    expected_pages = set(range(1, len(pdf_page_texts_value) + 1))
    output_pages = {page.get("page_number") for page in pages if isinstance(page, dict)}
    page_number_accuracy_score = pct(
        len(expected_pages.intersection(output_pages)), len(expected_pages)
    )

    internal_checks = {
        "requirements_match_page_aggregation": requirement_counter(top_requirements)
        == requirement_counter(page_requirements),
        "section_format_valid": section_format_valid(top_requirements),
        "cross_references_resolve": cross_references_resolve(document),
        "figures_match_page_aggregation": Counter(
            normalise_text(item.get("caption"))
            for item in document.get("figures", [])
            if isinstance(item, dict) and item.get("caption")
        )
        == Counter(
            normalise_text(item.get("caption"))
            for page in pages
            if isinstance(page, dict)
            for item in page.get("figures", [])
            if isinstance(item, dict) and item.get("caption")
        ),
        "tables_have_valid_pages": all(
            isinstance(item, dict) and item.get("page") in output_pages
            for item in document.get("tables", [])
            if isinstance(document.get("tables"), list)
        ),
    }
    json_internal_consistency_score = pct(
        sum(internal_checks.values()), len(internal_checks)
    )

    if gold_document is not None:
        gold_requirements = gold_document.get("requirements", [])
        gold_requirements = (
            gold_requirements if isinstance(gold_requirements, list) else []
        )
        requirement_f1_score = f1_from_counters(
            requirement_counter(gold_requirements),
            requirement_counter(top_requirements),
        )
        figure_caption_f1_score = f1_from_counters(
            Counter(
                normalise_text(item.get("caption"))
                for item in gold_document.get("figures", [])
                if isinstance(item, dict) and item.get("caption")
            ),
            Counter(
                normalise_text(item.get("caption"))
                for item in document.get("figures", [])
                if isinstance(item, dict) and item.get("caption")
            ),
        )
        table_caption_f1_score = f1_from_counters(
            Counter(
                normalise_text(item.get("caption"))
                for item in gold_document.get("tables", [])
                if isinstance(item, dict) and item.get("caption")
            ),
            Counter(
                normalise_text(item.get("caption"))
                for item in document.get("tables", [])
                if isinstance(item, dict) and item.get("caption")
            ),
        )
        component_scores = {
            "requirement_f1_score": requirement_f1_score,
            "figure_caption_f1_score": figure_caption_f1_score,
            "table_caption_f1_score": table_caption_f1_score,
            "page_text_fidelity_score": page_text_fidelity_score,
            "json_internal_consistency_score": json_internal_consistency_score,
        }
        formula = "mean(requirement_f1, figure_caption_f1, table_caption_f1, page_text_fidelity, json_internal_consistency)"
    else:
        category_priority_matches = 0
        category_priority_checks = 0
        for req in top_requirements:
            if not isinstance(req, dict):
                continue
            text = req.get("text")
            category = req.get("category")
            if text and category:
                category_priority_checks += 1
                if (
                    category == classify_requirement_scored(str(text))
                    and category in VALID_REQUIREMENT_CATEGORIES
                ):
                    category_priority_matches += 1
        category_consistency_priority_score = pct(
            category_priority_matches, category_priority_checks
        )

        component_scores = {
            "page_text_fidelity_score": page_text_fidelity_score,
            "requirement_traceability_score": requirement_traceability_score,
            "category_consistency_score": category_consistency_score,
            "page_number_accuracy_score": page_number_accuracy_score,
            "json_internal_consistency_score": json_internal_consistency_score,
            "category_consistency_priority_score": category_consistency_priority_score,
            "axi_signal_fidelity_score": axi_signal_fidelity_score(
                pdf_page_texts_value, top_requirements
            ),
            "riscv_csr_fidelity_score": riscv_csr_fidelity_score(
                pdf_page_texts_value, top_requirements
            ),
        }
        formula = "mean(page_text_fidelity, requirement_traceability, category_consistency, page_number_accuracy, json_internal_consistency, category_consistency_priority, axi_signal_fidelity, riscv_csr_fidelity)"

    return Score(
        name="accuracy",
        percentage=mean(component_scores.values()),
        formula=formula,
        details=component_scores,
    )


def score_table_figure_capture(
    document: dict[str, Any], pdf, pdf_page_texts_value: list[str], json_path: Path
) -> Score:
    expected_tables_by_page = expected_table_counts(pdf)
    captured_tables_by_page = page_count_counter(
        document.get("tables", []) if isinstance(document.get("tables"), list) else [],
        "page",
    )
    table_detection_f1_score = f1_from_counters(
        expected_tables_by_page, captured_tables_by_page
    )

    expected_table_caption_values = expected_captions(pdf_page_texts_value, TABLE_REGEX)
    captured_table_caption_values = captured_captions(document, "table_captions")
    table_caption_f1_score = f1_from_counters(
        expected_table_caption_values, captured_table_caption_values
    )

    table_records = document.get("tables", [])
    table_records = table_records if isinstance(table_records, list) else []
    existing_files = 0
    for table in table_records:
        if not isinstance(table, dict):
            continue
        csv_file = table.get("csv_file")
        if not csv_file:
            continue
        content_root = json_path.parent.resolve()
        candidate = Path(csv_file)
        candidate = (
            candidate.resolve()
            if candidate.is_absolute()
            else (content_root / candidate).resolve()
        )
        # Uploaded JSON must not turn a file-existence score into a probe of
        # unrelated host paths.
        if candidate.is_relative_to(content_root) and candidate.is_file():
            existing_files += 1
    table_file_empty_score = (
        100.0 if sum(expected_tables_by_page.values()) == 0 else 0.0
    )
    table_file_existence_score = pct(
        existing_files, len(table_records), empty_is=table_file_empty_score
    )

    expected_figure_caption_values = expected_captions(
        pdf_page_texts_value, FIGURE_REGEX
    )
    captured_figure_caption_values = captured_captions(document, "figures")
    figure_caption_f1_score = f1_from_counters(
        expected_figure_caption_values, captured_figure_caption_values
    )

    expected_images_by_page = expected_image_counts(pdf)
    captured_images = []
    pages = document.get("pages", [])
    for page in pages if isinstance(pages, list) else []:
        captured_images.extend(
            page.get("images", [])
            if isinstance(page, dict) and isinstance(page.get("images"), list)
            else []
        )
    captured_images_by_page = page_count_counter(captured_images, "page")
    image_capture_f1_score = f1_from_counters(
        expected_images_by_page, captured_images_by_page
    )

    component_scores = {
        "table_detection_f1_score": table_detection_f1_score,
        "table_caption_f1_score": table_caption_f1_score,
        "table_file_existence_score": table_file_existence_score,
        "figure_caption_f1_score": figure_caption_f1_score,
        "image_capture_f1_score": image_capture_f1_score,
    }

    return Score(
        name="table_figure_capture",
        percentage=mean(component_scores.values()),
        formula="mean(table_detection_f1, table_caption_f1, table_file_existence, figure_caption_f1, image_capture_f1)",
        details=component_scores,
    )


def status(percentage: float, threshold: float) -> str:
    return "pass" if percentage >= threshold else "fail"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    json_path = Path(args.json).expanduser().resolve()
    document = load_json(json_path)

    pdf_path = (
        Path(args.pdf).expanduser().resolve()
        if args.pdf
        else infer_pdf_path(json_path, document)
    )
    pdf = open_pdf(pdf_path)
    source_page_texts = pdf_page_texts(pdf)

    gold_document = (
        load_json(Path(args.gold_json).expanduser().resolve())
        if args.gold_json
        else None
    )

    try:
        scores = [
            score_completeness(document, source_page_texts),
            score_accuracy(document, source_page_texts, gold_document),
            score_table_figure_capture(document, pdf, source_page_texts, json_path),
        ]
    finally:
        if pdf is not None:
            pdf.close()

    score_report = {
        score.name: {
            "percentage": round(score.percentage, 2),
            "status": status(score.percentage, args.threshold),
            "formula": score.formula,
            "details": {key: round(value, 2) for key, value in score.details.items()},
        }
        for score in scores
    }
    overall_percentage = mean(score.percentage for score in scores)

    return {
        "inputs": {
            "json": str(json_path),
            "pdf": str(pdf_path) if pdf_path else None,
            "gold_json": (
                str(Path(args.gold_json).expanduser().resolve())
                if args.gold_json
                else None
            ),
            "threshold": args.threshold,
        },
        "scores": score_report,
        "overall_percentage": round(overall_percentage, 2),
        "overall_status": status(overall_percentage, args.threshold),
    }


def run_quality_check(
    json_path: str | Path,
    *,
    pdf_path: str | Path | None = None,
    gold_json_path: str | Path | None = None,
    threshold: float = 95.0,
) -> dict[str, Any]:
    """Run the checker without requiring callers to construct CLI arguments."""

    if not 0 <= threshold <= 100:
        raise ValueError("Quality threshold must be between 0 and 100.")

    args = argparse.Namespace(
        json=str(json_path),
        pdf=str(pdf_path) if pdf_path else None,
        gold_json=str(gold_json_path) if gold_json_path else None,
        threshold=threshold,
        report_json=None,
    )
    return build_report(args)


def print_report(report: dict[str, Any]) -> None:
    print("Extractor Quality Check")
    print("=======================")
    print(f"JSON: {report['inputs']['json']}")
    print(f"PDF:  {report['inputs']['pdf'] or 'not supplied/found'}")
    if report["inputs"]["gold_json"]:
        print(f"Gold: {report['inputs']['gold_json']}")
    print()

    for name, score in report["scores"].items():
        print(f"{name}: {score['percentage']:.2f}% - {score['status']}")
        print(f"  formula: {score['formula']}")
        for detail_name, detail_value in score["details"].items():
            print(f"  {detail_name}: {detail_value:.2f}%")
        print()

    print(f"overall: {report['overall_percentage']:.2f}% - {report['overall_status']}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check extractor JSON/CSV output quality."
    )
    parser.add_argument(
        "--json", required=True, help="Path to extractor document.json output."
    )
    parser.add_argument(
        "--pdf",
        help="Path to the source PDF. If omitted, the checker tries to infer it.",
    )
    parser.add_argument(
        "--gold-json",
        help="Optional manually checked reference JSON for true accuracy/F1 scoring.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=95.0,
        help="Pass/fail threshold percentage. Default: 95.",
    )
    parser.add_argument(
        "--report-json", help="Optional path to write the quality report as JSON."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report = build_report(args)
    print_report(report)

    if args.report_json:
        output_path = Path(args.report_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")

    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
